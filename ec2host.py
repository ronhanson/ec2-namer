#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu
"""
:Author: Ronan Delacroix
:Copyright: (c) 2018 Ronan Delacroix
"""
import tbx.aws


def check_ec2_hostname_tags():
    ec2 = tbx.aws.EC2()

    instance = ec2.current_instance()
    tags = ec2.get_instance_tags(instance)

    group = tags.get('group')
    number = tags.get('number')
    instance_zone = tags.get('zone')
    env = tags.get('environment')

    instances_like_me = ec2.get_instances_by_tags(tags={
        'group': group,
        'number': number,
        'zone': instance_zone,
        'environment': env
    })

    other_instances = [inst for inst in instances_like_me if inst.id != instance.id]

    if len(other_instances) >= 1:
        # found another instance like me, so I am going to change tags and edit my name
        group_instances = ec2.get_instances_by_tags(tags={
            'group': group,
            'zone': instance_zone,
            'environment': env
        })
        group_instances_numbers = [ec2.get_instance_tags(inst).get('number') for inst in group_instances if inst.id != instance.id]
        group_instances_numbers.sort()
        new_lowest_available_number = None
        for i in range(1, 999):
            if "%04d" % i not in group_instances_numbers:
                new_lowest_available_number = "%04d" % i
                break
        suffix = '.' + env
        if env == 'prod':
            suffix = ''
        new_tags = {
            'group': group,
            'number': new_lowest_available_number,
            'zone': instance_zone,
            'environment': env,
            'internal-hostname': "{}-{}{}".format(group, new_lowest_available_number, suffix),
            'public-hostname': "{}-{}{}".format(group, new_lowest_available_number, suffix),
            'Name': "{}-{}{}".format(group, new_lowest_available_number, suffix),
            'fullname': "{}-{}{}.{}".format(group, new_lowest_available_number, suffix, instance_zone)
        }
        # Update tags of current instance
        ec2.create_tags(instance, tags=new_tags)

        instance.reload()
        return True
    else:
        return False


def create_public_routes():
    ec2 = tbx.aws.EC2()

    instance = ec2.current_instance()
    tags = ec2.get_instance_tags(instance)

    instance_zone = tags.get('zone', None)
    public_hostname = tags.get('public-hostname', None)
    internal_hostname = tags.get('internal-hostname', None)

    if instance_zone and public_hostname:
        r53 = tbx.aws.Route53()
        zone_id = r53.get_zone_id(name=instance_zone)

        dns_record_name = public_hostname+'.'+instance_zone+'.'

        r53.delete_record(zone_id, dns_record_name)  # if a route already exists, delete it
        r53.create_record(zone_id, dns_record_name, instance.public_ip_address, type='A', ttl=300)

    return internal_hostname


