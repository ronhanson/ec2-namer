from setuptools import setup, find_packages
import os
import re

if os.environ.get('USER', '') == 'vagrant':
    del os.link

requirements = [r.strip() for r in open('requirements.txt').readlines() if not r.startswith('--')]
requirements = [r if ('git+' not in r) else re.sub(r".*egg=(.*)", r"\1", r).strip() for r in requirements]

setup(
    name='ec2-namer',
    version=open('VERSION.txt').read().strip(),
    author='Ronan Delacroix',
    author_email='ronan.delacroix@gmail.com',
    url='https://github.com/ronhanson/ec2-namer',
    py_modules=['ec2host'],
    package_data={},
    scripts=['bin/ec2-rename'],
    license=open('LICENCE.txt').read().strip(),
    description='EC2 Namer - AWS EC2 host naming tool. Modifies hostname and public DNS routes based on EC2 tags.',
    long_description=open('README.md').read().strip(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        'Topic :: Software Development :: Libraries',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
    ],
)
