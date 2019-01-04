#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
:Author: Ronan Delacroix
:Copyright: (c) 2018 Ronan Delacroix
"""
import logging
import tbx.aws
from operator import itemgetter


def check_ec2_hostname_tags():
    ec2 = tbx.aws.EC2()

    instance = ec2.current_instance()
    tags = ec2.get_instance_tags(instance)

    logging.info("Checking EC2 instance tags of %s" % str(instance.id))

    public_zone = tags.get('public-zone')
    private_zone = tags.get('private-zone')
    group = tags.get('group')
    number = tags.get('number', "0001")
    env = tags.get('environment', None)
    suffix = '.' + str(env)
    if not env or env == 'prod' or env == 'production':
        suffix = ''

    if not group or not private_zone:
        logging.error('No group or zone tag found for instance %s' % instance.id)
        return None

    logging.info("Current instance tags : %s" % (', '.join(['%s=%s' % (str(k), str(v)) for k, v in tags.items()])))

    filters = {
        'private-zone': private_zone,
        'group': group,
        'number': number
    }
    if suffix:
        filters['environment'] = env
    instances_like_me = ec2.get_instances_by_tags(tags=filters)

    other_instances = [
        inst for inst in instances_like_me
        if inst.id != instance.id and inst.state.get('Name', 'running') == 'running'
    ]

    if len(other_instances) >= 1:
        logging.warning("Found %d instances having same group and number (%s). Updating EC2 tags." % (
            len(other_instances), ', '.join([i.id for i in other_instances])
        ))

        # found another instance like me, so I am going to change tags and edit my name
        filters = {
            'private-zone': private_zone,
            'group': group
        }
        if suffix:
            filters['environment'] = env
        group_instances = ec2.get_instances_by_tags(tags=filters)
        group_instances_numbers = [
            ec2.get_instance_tags(inst).get('number', "9999")
            for inst in group_instances
            if inst.id != instance.id and inst.state.get('Name', 'running') == 'running'
        ]
        group_instances_numbers = sorted(map(str, group_instances_numbers))
        new_lowest_available_number = None
        for i in range(1, 9999):
            if "%04d" % i not in group_instances_numbers:
                new_lowest_available_number = "%04d" % i
                break
        number = new_lowest_available_number

    public_hostname = "{}-{}{}".format(group, number, suffix)
    private_hostname = public_hostname.replace('.', '-')
    new_tags = {
        'number': number,
        "hostname": private_hostname,
        'Name': "{}.{}".format(public_hostname, public_zone)
    }

    # Update tags of current instance
    ec2.create_tags(instance, tags=new_tags)

    logging.info("Instance %s updated" % str(instance.id))

    instance.reload()
    updated_tags = ec2.get_instance_tags(instance)
    logging.info("New instance tags : %s" % (', '.join(['%s=%s' % (str(k), str(v)) for k, v in updated_tags.items()])))

    return private_hostname


def create_dns_record(r53, zone, dns, ip_address):

    if type(ip_address) is list:
        ip_address = [ip for ip in ip_address if ip]  # filter None if multiple IP addresses given as param

    zone_id = r53.get_zone_id(name=zone)

    dns_record_name = dns + '.' + zone + '.'

    r53.delete_record(zone_id, dns_record_name)  # if a route already exists, delete it
    r53.create_record(zone_id, dns_record_name, ip_address, record_type='A', ttl=300)
    logging.info("DNS record created/updated - %s %s => %s" % (zone_id, dns_record_name, str(ip_address)))


def create_public_routes():
    ec2 = tbx.aws.EC2()

    instance = ec2.current_instance()
    tags = ec2.get_instance_tags(instance)

    logging.info("Ensuring public routes for instance %s" % str(instance.id))

    public_zone = tags.get('public-zone', None)
    private_zone = tags.get('private-zone', None)
    number = tags.get('number', None)
    group = tags.get('group', None)
    env = tags.get('environment', None)
    suffix = '.' + str(env)
    if not env or env == 'prod' or env == 'production':
        suffix = ''

    if not group or not number:
        logging.error('No group or number tag found for instance %s' % instance.id)
        return None

    public_hostname = "{}-{}{}".format(group, number, suffix)
    private_hostname = public_hostname.replace('.', '-')
    service_name = "{}{}".format(group, suffix)

    r53 = tbx.aws.Route53()

    if private_zone:
        create_dns_record(r53, private_zone, private_hostname, instance.private_ip_address)
        ec2.create_tag(instance, key='private-dns', value="{}.{}".format(private_hostname, private_zone))

    if public_zone:
        create_dns_record(r53, public_zone, public_hostname, instance.public_ip_address)
        ec2.create_tag(instance, key='public-dns', value="{}.{}".format(public_hostname, public_zone))

    instance.reload()
    tags = ec2.get_instance_tags(instance)

    ##
    # Create / Update service dns entries
    ##
    filters = {
        'private-zone': private_zone,
        'group': group
    }
    if suffix:
        filters['environment'] = env
    instances_same_group = ec2.get_instances_by_tags(tags=filters)

    if private_zone:
        private_ip_adresses = [
            (int(ec2.get_instance_tags(i).get('number', "9999")), i.private_ip_address)
            for i in instances_same_group
            if i.private_ip_address and i.state.get('Name', 'running') == 'running'
        ]
        private_ip_adresses = [ip for i, ip in sorted(private_ip_adresses, key=itemgetter(0)) if ip]
        create_dns_record(r53, private_zone, service_name, private_ip_adresses)
        ec2.create_tag(instance, key='private-service-dns', value="{}.{}".format(service_name, private_zone))

    if public_zone:
        public_ip_adresses = [
            (int(ec2.get_instance_tags(i).get('number', "9999")), i.public_ip_address)
            for i in instances_same_group
            if i.public_ip_address and i.state.get('Name', 'running') == 'running'
        ]
        public_ip_adresses = [ip for i, ip in sorted(public_ip_adresses, key=itemgetter(0)) if ip]
        create_dns_record(r53, public_zone, service_name, public_ip_adresses)
        ec2.create_tags(instance, key='public-service-dns', value="{}.{}".format(service_name, public_zone))

    instance.reload()
    tags = ec2.get_instance_tags(instance)

    return tags


