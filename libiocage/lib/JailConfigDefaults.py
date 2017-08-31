import json
import os.path

import libiocage.lib.helpers


class JailConfigDefaults(dict):

    DEFAULTS = {
        "id": None,
        "basejail": False,
        "defaultrouter": None,
        "defaultrouter6": None,
        "mac_prefix": "02ff60",
        "vnet": False,
        "ip4": "new",
        "ip4_saddrsel": 1,
        "ip6": "new",
        "ip6_saddrsel": 1,
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
        "tags": []
    }

    def __init__(self, file, logger):
        self.logger = logger
        dict.__init__(self, JailConfigDefaults.DEFAULTS)
        self.file = file
        try:
            self.read()
        except:
            pass

    def read(self):

        if (self.file is None) or not isinstance(self.file, str):
            self._file = None
            self.clear()
            return

        if not os.path.isfile(self.file):
            raise libiocage.lib.errors.DefaultConfigNotFound(
                config_file_path=self.file,
                logger=None
            )

        if self.logger:
            self.logger.debug(f"Reading default config from {self.file}")

        f = open(self.file, "r")
        data = json.load(f)
        f.close()

        for key, value in data.items():
            self[key] = value

    def clear(self):
        dict.clear(self)
        dict.__init__(self, JailConfigDefaults.DEFAULTS)
