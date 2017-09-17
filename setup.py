# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import os.path
import sys
import fastentrypoints
from setuptools import find_packages, setup
from pip.req import parse_requirements

reqs = list(parse_requirements("requirements.txt", session="iocage"))
install_requires = list(map(lambda x: f"{x.name}{x.specifier}", reqs))
dependency_links = list(map(
    lambda x: str(x.link), 
    filter(lambda x: x.link, reqs)
))

if os.path.isdir("/usr/local/etc/init.d"):
    _data = [('/usr/local/etc/init.d', ['rc.d/ioc'])]
else:
    _data = [('/usr/local/etc/rc.d', ['rc.d/ioc'])]

if sys.version_info < (3, 6):
    exit("Only Python 3.6 and higher is supported.")

setup(
    name='iocage',
    license='BSD',
    version='0.2.12',
    description='A Python library to manage jails with iocage',
    keywords='FreeBSD jail iocage',
    author='iocage Contributors',
    author_email='authors@iocage.io',
    url='https://github.com/iocage/libiocage',
    python_requires='>=3.6',
    packages=find_packages(),
    package_data={'': ['fastentrypoints.py']},
    include_package_data=True,
    install_requires=install_requires,
    dependency_links=dependency_links,
    setup_requires=['pytest-runner'],
    entry_points={
        'console_scripts': [
            'ioc=iocage.cli:cli'
        ]
    },
    data_files=_data,
    tests_require=['pytest', 'pytest-cov', 'pytest-pep8']
)
