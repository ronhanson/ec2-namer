EC2 Namer - AWS EC2 host naming tool. 
=====================================


About
-----

Startup script - Modifies tags, hostname and public DNS routes based on EC2 some tags

Tag your ec2 instance with the following : 

 - 'group': 'compute' / 'webserver'
 - 'number': '0001'
 - 'zone': 'my-dns.com'
 - 'environment': 'dev' / 'prod'

If another machine is found with same tags, the number tag will be incremented (or updated with non existing one at least).
You can then duplicate an instance with its tags, and these tags will be updated to make the host unique (hostname and DNS route pointing to it).

And a public route in the form of {group}-{number}.{env}.{zone}. For example : webserver-0001.dev.my_dns.com

Internal hostname will also be set to {group}-{number}.{env} like webserver-0001.dev.

Works on linux and windows (but needs a reboot once in windows after changing hostname).

Project url : https://github.com/ronhanson/ec2-namer


Usage
-----

Add "python3 ec2-rename" at startup.

Compatibility
-------------

This libraries are used most on Linux and Windows systems.

This libraries are compatibles with Python 3.4+.

Mainly tested on 3.6.


Author & Licence
----------------

Copyright (c) 2010-2015 Ronan Delacroix

This program is released under MIT Licence. Feel free to use it or part of it anywhere you want.
