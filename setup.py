# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""Installs libiocage using easy_install."""
import sys
from setuptools import find_packages, setup
from setuptools.command import easy_install
try:
    from pip._internal.req import parse_requirements
except ModuleNotFoundError:
    from pip.req import parse_requirements

def _read_requirements(filename: str="requirements.txt") -> None:
    reqs = list(parse_requirements(filename, session="iocage"))
    return dict(
        install_requires=list(map(lambda x: f"{x.name}{x.specifier}", reqs)),
        dependency_links=list(map(
            lambda x: str(x.link),
            filter(lambda x: x.link, reqs)
        ))
    )

iocage_requirements = _read_requirements("requirements.txt")
ioc_requirements = _read_requirements("requirements-ioc.txt")

TEMPLATE = '''\
# -*- coding: utf-8 -*-
# EASY-INSTALL-ENTRY-SCRIPT: '{0}'
__requires__ = '{0}'
import sys

from ioc import cli

if __name__ == '__main__':
    sys.dd:exit(cli())'''


@classmethod
def get_args(cls, dist, header=None):
    """Handle arguments for easy_install."""
    if header is None:
        header = cls.get_header()

    script_text = TEMPLATE.format(str(dist.as_requirement()))
    args = cls._get_script_args("console", "ioc", header, script_text)

    for res in args:
        yield res


easy_install.ScriptWriter.get_args = get_args


if sys.version_info < (3, 6):
    exit("Only Python 3.6 and higher is supported.")

setup(
    name='iocage',
    license='BSD',
    version='0.3.0',
    description='A Python library to manage jails with iocage',
    keywords='FreeBSD jail iocage',
    author='iocage Contributors',
    author_email='authors@iocage.io',
    url='https://github.com/iocage/libiocage',
    python_requires='>=3.6',
    packages=find_packages(include=["iocage", "iocage.*"]),
    include_package_data=True,
    install_requires=iocage_requirements["install_requires"],
    dependency_links=iocage_requirements["dependency_links"],
    setup_requires=['pytest-runner'],
    tests_require=['pytest', 'pytest-cov', 'pytest-pep8']
)

setup(
    name='ioc',
    license='BSD',
    version='0.3.0',
    description='A Python library to manage jails with iocage',
    keywords='FreeBSD jail iocage',
    author='iocage Contributors',
    author_email='authors@iocage.io',
    url='https://github.com/iocage/libiocage',
    python_requires='>=3.6',
    packages=find_packages(include=["ioc", "ioc.*"]),
    include_package_data=True,
    install_requires=iocage_requirements["install_requires"],
    dependency_links=iocage_requirements["dependency_links"],
    entry_points={
        'console_scripts': [
            'ioc=ioc:cli'
        ]
    }
)
