# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
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
"""Installs libioc using setuptools."""
import sys
import typing
from setuptools import find_packages, setup
try:
    from pip._internal.req import parse_requirements
except ModuleNotFoundError:
    from pip.req import parse_requirements

try:
    import setuptools_scm.integration
    setuptools_scm.integration.find_files = lambda _: []
except ImportError:
    pass


def _read_requirements(
    filename: str="requirements.txt"
) -> typing.Dict[str, typing.List[str]]:
    reqs = list(parse_requirements(filename, session="libioc"))
    return dict(
        install_requires=list(map(lambda x: f"{x.name}{x.specifier}", reqs)),
        dependency_links=list(map(
            lambda x: str(x.link),
            filter(lambda x: x.link, reqs)
        ))
    )


ioc_requirements = _read_requirements("requirements.txt")

if sys.version_info < (3, 6):
    exit("Only Python 3.6 and higher is supported.")

with open("libioc/VERSION", "r") as f:
    version = f.read().split()[0]

setup(
    name='libioc',
    license='BSD',
    version=version,
    description='A Python library to manage jails with ioc{age,cell}',
    keywords='FreeBSD jail ioc',
    author='ioc Contributors',
    author_email='authors@libioc.io',
    url='https://github.com/bsdci/libioc',
    python_requires='>=3.6',
    packages=find_packages(include=["libioc", "libioc.*"]),
    package_data={'': ['VERSION']},
    include_package_data=True,
    install_requires=ioc_requirements["install_requires"],
    dependency_links=ioc_requirements["dependency_links"],
    # setup_requires=['pytest-runner'],
    tests_require=['pytest', 'pytest-cov', 'pytest-pep8']
)

