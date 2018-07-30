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
    private_hostname = tags.get('private-hostname', None)
    public_hostname = tags.get('public-hostname', None)

    if not group or not private_zone:
        logging.error('No group or zone tag found for instance %s' % instance.id)
        return None

    logging.info("Current instance tags : %s" % (', '.join(['%s=%s' % (str(k), str(v)) for k, v in tags.items()])))

    instances_like_me = ec2.get_instances_by_tags(tags={
        'private-zone': private_zone,
        'group': group,
        'number': number,
        'environment': env
    })

    other_instances = [inst for inst in instances_like_me if inst.id != instance.id]
    if len(other_instances) >= 1 or not private_hostname or not public_hostname:
        logging.warning("Found %d instances having same group and number (%s). Updating EC2 tags." % (
            len(other_instances), ', '.join([i.id for i in other_instances])
        ))

        # found another instance like me, so I am going to change tags and edit my name
        group_instances = ec2.get_instances_by_tags(tags={
            'group': group,
            'private-zone': private_zone,
            'environment': env
        })
        group_instances_numbers = [ec2.get_instance_tags(inst).get('number') for inst in group_instances if
                                   inst.id != instance.id]
        group_instances_numbers.sort()
        new_lowest_available_number = None
        for i in range(1, 999):
            if "%04d" % i not in group_instances_numbers:
                new_lowest_available_number = "%04d" % i
                break
        suffix = '.' + env
        if env == 'prod' or env == 'production':
            suffix = ''
        public_hostname = "{}-{}{}".format(group, new_lowest_available_number, suffix)
        private_hostname = public_hostname.replace('.', '-')
        group_dns = "{}{}".format(group, suffix)
        new_tags = {
            'group': group,
            'number': new_lowest_available_number,
            'public-zone': public_zone,
            'private-zone': private_zone,
            'environment': env,
            'private-hostname': private_hostname,
            'public-hostname': public_hostname,
            'service-name': group_dns,
            'Name': "{}.{}".format(public_hostname, public_zone)
        }
        logging.info("New instance tags : %s" % (', '.join(['%s=%s' % (str(k), str(v)) for k, v in new_tags.items()])))
        # Update tags of current instance
        ec2.create_tags(instance, tags=new_tags)

        instance.reload()
        logging.info("Instance %s updated" % str(instance.id))
        return True
    else:
        return False


def create_dns_record(r53, zone, dns, ip_address):
    zone_id = r53.get_zone_id(name=zone)

    dns_record_name = dns + '.' + zone + '.'

    r53.delete_record(zone_id, dns_record_name)  # if a route already exists, delete it
    r53.create_record(zone_id, dns_record_name, ip_address, type='A', ttl=300)
    logging.info("DNS record created/updated - %s %s => %s" % (zone, dns_record_name, str(ip_address)))


def create_public_routes():
    ec2 = tbx.aws.EC2()

    instance = ec2.current_instance()
    tags = ec2.get_instance_tags(instance)

    logging.info("Ensuring public routes for instance %s" % str(instance.id))

    public_zone = tags.get('public-zone', None)
    public_hostname = tags.get('public-hostname', None)

    private_zone = tags.get('private-zone', None)
    private_hostname = tags.get('private-hostname', None)

    r53 = tbx.aws.Route53()

    create_dns_record(r53, private_zone, private_hostname, instance.private_ip_address)
    create_dns_record(r53, public_zone, public_hostname, instance.public_ip_address)

    ec2.create_tags(instance, tags={
        'public-dns': "{}.{}".format(public_hostname, public_zone),
        'private-dns': "{}.{}".format(private_hostname, private_zone)
    })
    instance.reload()
    tags = ec2.get_instance_tags(instance)

    # Create / Update service dns entries

    group = tags.get('group')
    env = tags.get('environment', None)
    service_name = tags.get('service-name', None)

    instances_same_group = ec2.get_instances_by_tags(tags={
        'private-zone': private_zone,
        'group': group,
        'environment': env
    })

    public_ip_adresses = [(int(ec2.get_instance_tags(i).get('number')), i.public_ip_address) for i in instances_same_group]
    private_ip_adresses = [(int(ec2.get_instance_tags(i).get('number')), i.private_ip_address) for i in instances_same_group]

    public_ip_adresses = [ip for i, ip in sorted(public_ip_adresses, key=itemgetter(0))]
    private_ip_adresses = [ip for i, ip in sorted(private_ip_adresses, key=itemgetter(0))]

    create_dns_record(r53, public_zone, service_name, public_ip_adresses)
    create_dns_record(r53, private_zone, service_name, private_ip_adresses)

    ec2.create_tags(instance, tags={
        'public-service-dns': "{}.{}".format(service_name, public_zone),
        'private-service-dns': "{}.{}".format(service_name, private_zone)
    })
    instance.reload()
    tags = ec2.get_instance_tags(instance)

    return tags


