#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
:Author: Ronan Delacroix
:Copyright: (c) 2018 Ronan Delacroix
"""
import logging
import tbx.aws


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
        if env == 'prod':
            suffix = ''
        public_hostname = "{}-{}{}".format(group, new_lowest_available_number, suffix)
        private_hostname = public_hostname.replace('.', '-')
        new_tags = {
            'group': group,
            'number': new_lowest_available_number,
            'public-zone': public_zone,
            'private-zone': private_zone,
            'environment': env,
            'private-hostname': private_hostname,
            'public-hostname': public_hostname,
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

    if private_zone and private_hostname:
        private_zone_id = r53.get_zone_id(name=private_zone)

        private_dns_record_name = private_hostname + '.' + private_zone + '.'

        r53.delete_record(private_zone_id, private_dns_record_name)  # if a route already exists, delete it
        r53.create_record(private_zone_id, private_dns_record_name, instance.private_ip_address, type='A', ttl=300)
        logging.info("Internal DNS records created/updated - %s %s => %s (%s)" % (private_zone, private_dns_record_name, instance.private_ip_address, instance.id))
    else:
        logging.error("Impossible to create internal routes as no private-zone or private-hostname tags have been found for instance %s." % instance.id)
        return None

    if public_zone and public_hostname:
        public_zone_id = r53.get_zone_id(name=public_zone)

        public_dns_record_name = public_hostname + '.' + public_zone + '.'

        r53.delete_record(public_zone_id, public_dns_record_name)  # if a route already exists, delete it
        r53.create_record(public_zone_id, public_dns_record_name, instance.public_ip_address, type='A', ttl=300)
        logging.info("Public DNS records created/updated - %s %s => %s (%s)" % (public_zone, public_dns_record_name, instance.public_ip_address, instance.id))
    else:
        logging.error("Impossible to create public routes as no public-hostname or private-hostname tags have been found for instance %s." % instance.id)
        return None

    ec2.create_tags(instance, tags={
        'public-dns': "{}.{}".format(public_hostname, public_zone),
        'private-dns': "{}.{}".format(private_hostname, private_zone)
    })
    instance.reload()
    tags = ec2.get_instance_tags(instance)

    return tags


