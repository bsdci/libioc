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

class JailStateData:

  # jail.identifier
  name: str;

  devfs_ruleset: typing.Optional[str];
  dying: typing.Optional[str];
  enforce_statfs: typing.Optional[str];
  host: typing.Optional[str];
  ip4: typing.Optional[str];
  ip6: typing.Optional[str];
  jid: typing.Optional[str];
  osreldate: typing.Optional[str];
  osrelease: typing.Optional[str];
  parent: typing.Optional[str];
  path: typing.Optional[str];
  persist: typing.Optional[str];
  securelevel: typing.Optional[str];
  sysvmsg: typing.Optional[str];
  sysvsem: typing.Optional[str];
  sysvshm: typing.Optional[str];
  vnet: typing.Optional[str];
  allow.chflags: typing.Optional[str];
  allow.mount: typing.Optional[str];
  allow.mount.devfs: typing.Optional[str];
  allow.mount.fdescfs: typing.Optional[str];
  allow.mount.linprocfs: typing.Optional[str];
  allow.mount.linsysfs: typing.Optional[str];
  allow.mount.nullfs: typing.Optional[str];
  allow.mount.procfs: typing.Optional[str];
  allow.mount.tmpfs: typing.Optional[str];
  allow.mount.zfs: typing.Optional[str];
  allow.quotas: typing.Optional[str];
  allow.raw_sockets: typing.Optional[str];
  allow.set_hostname: typing.Optional[str];
  allow.socket_af: typing.Optional[str];
  allow.sysvipc: typing.Optional[str];
  children.cur: typing.Optional[str];
  children.max: typing.Optional[str];
  cpuset.id: typing.Optional[str];
  host.domainname: typing.Optional[str];
  host.hostid: typing.Optional[str];
  host.hostname: typing.Optional[str];
  host.hostuuid: typing.Optional[str];
  ip4.saddrsel: typing.Optional[str];
  ip6.saddrsel: typing.Optional[str];

class JailState(JailStateData):

  def __init__(
    self,
    data: JailStateData
  ) -> None:


    self.name = 

  def update(self) -> None:

    if self.name 

    try:
        import json
        stdout = subprocess.check_output([
            "/usr/sbin/jls",
            "-j",
            self.name,
            "-v",
            "-h",
            "--libxo=json"
        ], shell=False, stderr=subprocess.DEVNULL)  # nosec TODO use helper
        output = stdout.decode().strip()

        self.jail_state = json.loads(output)["jail-information"]["jail"][0]

    except:
        self.jail_state = {}

