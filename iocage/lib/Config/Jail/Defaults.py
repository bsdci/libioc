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
import typing

import iocage.lib.Config.Jail.BaseConfig


class JailConfigDefaults(iocage.lib.Config.Jail.BaseConfig.BaseConfig):

    user_properties: set = set()

    data: dict = {
        "id": None,
        "release": None,
        "boot": False,
        "priority": 0,
        "legacy": False,
        "priority": 0,
        "basejail": False,
        "defaultrouter": None,
        "defaultrouter6": None,
        "mac_prefix": "02ff60",
        "vnet": False,
        "interfaces": [],
        "ip4": "new",
        "ip4_saddrsel": 1,
        "ip4_addr": None,
        "ip6": "new",
        "ip6_saddrsel": 1,
        "ip6_addr": None,
        "resolver": "/etc/resolv.conf",
        "host_domainname": "none",
        "devfs_ruleset": 4,
        "enforce_statfs": 2,
        "children_max": 0,
        "allow_set_hostname": 1,
        "allow_sysvipc": 0,
        "allow_raw_sockets": 0,
        "allow_chflags": 0,
        "allow_mount": 0,
        "allow_mount_devfs": 0,
        "allow_mount_nullfs": 0,
        "allow_mount_procfs": 0,
        "allow_mount_zfs": 0,
        "allow_mount_tmpfs": 0,
        "allow_quotas": 0,
        "allow_socket_af": 0,
        "sysvmsg": "new",
        "sysvsem": "new",
        "sysvshm": "new",
        "exec_clean": 1,
        "exec_fib": 1,
        "exec_prestart": "/usr/bin/true",
        "exec_start": "/bin/sh /etc/rc",
        "exec_poststart": "/usr/bin/true",
        "exec_prestop": "/usr/bin/true",
        "exec_stop": "/bin/sh /etc/rc.shutdown",
        "exec_poststop": "/usr/bin/true",
        "exec_timeout": "60",
        "stop_timeout": "30",
        "mount_devfs": "1",
        "mount_fdescfs": "1",
        "securelevel": "2",
        "tags": [],
        "jail_zfs": False
    }

    def clear(self):
        dict.clear(self)
        dict.__init__(self, JailConfigDefaults.DEFAULTS)

    def __setitem__(
        self,
        key: str,
        value: typing.Any,
        **kwargs
    ):

        out = super().__setitem__(key, value, **kwargs)
        self.user_properties.add(key)
        return out

    @property
    def user_data(self) -> dict:
        data = {}
        for prop in self.user_properties:
            data[prop] = self.data[prop]
        return data
