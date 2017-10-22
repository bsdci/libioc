class JailStateData:

  # jail.identifier
  name: str;

  devfs_ruleset?: str;
  dying?: str;
  enforce_statfs?: str;
  host?: str;
  ip4?: str;
  ip6?: str;
  jid?: str;
  osreldate?: str;
  osrelease?: str;
  parent?: str;
  path?: str;
  persist?: str;
  securelevel?: str;
  sysvmsg?: str;
  sysvsem?: str;
  sysvshm?: str;
  vnet?: str;
  allow.chflags?: str;
  allow.mount?: str;
  allow.mount.devfs?: str;
  allow.mount.fdescfs?: str;
  allow.mount.linprocfs?: str;
  allow.mount.linsysfs?: str;
  allow.mount.nullfs?: str;
  allow.mount.procfs?: str;
  allow.mount.tmpfs?: str;
  allow.mount.zfs?: str;
  allow.quotas?: str;
  allow.raw_sockets?: str;
  allow.set_hostname?: str;
  allow.socket_af?: str;
  allow.sysvipc?: str;
  children.cur?: str;
  children.max?: str;
  cpuset.id?: str;
  host.domainname?: str;
  host.hostid?: str;
  host.hostname?: str;
  host.hostuuid?: str;
  ip4.saddrsel?: str;
  ip6.saddrsel?: str;

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

