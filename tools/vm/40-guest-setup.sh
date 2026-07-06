#!/bin/sh
# Prepare the FreeBSD guest for running the libioc test suite.
# The script is idempotent.
# Root's login shell on FreeBSD is csh, so all nontrivial command
# sequences are piped into a POSIX shell on the guest instead of being
# passed as ssh command strings.
set -e
. "$(dirname "$0")/config.sh"

echo "Running the in-guest setup script."
${VM_SSH} sh -s <<'GUEST_SCRIPT'
set -e

echo "Synchronizing the clock."
service ntpd stop 2>/dev/null || true
ntpdate -b 0.freebsd.pool.ntp.org || ntpdate -b pool.ntp.org || true

echo "Configuring the package repository."
mkdir -p /usr/local/etc/pkg/repos
cat > /usr/local/etc/pkg/repos/FreeBSD.conf <<'REPO'
FreeBSD: { url: "pkg+https://pkg.FreeBSD.org/${ABI}/latest" }
REPO

echo "Bootstrapping pkg."
env ASSUME_ALWAYS_YES=yes pkg bootstrap -f
pkg update -f

echo "Detecting the python package prefix."
PYPKG="$(pkg search -q '^py3[0-9]*-libzfs' | head -n 1 | sed 's/-libzfs.*//')"
if [ -z "${PYPKG}" ]; then
    echo "Could not detect the python package prefix." >&2
    exit 1
fi
echo "Python package prefix: ${PYPKG}"

pkg install -y python3 "${PYPKG}-libzfs" "${PYPKG}-ucl" \
    "${PYPKG}-sqlite3" "${PYPKG}-setuptools" "${PYPKG}-pip" \
    git rsync ca_root_nss

echo "Mounting fdescfs."
grep -q fdescfs /etc/fstab || \
    echo "fdesc /dev/fd fdescfs rw 0 0" >> /etc/fstab
mount | grep -q "/dev/fd" || mount -t fdescfs null /dev/fd

echo "Enabling resource accounting for the rctl tests."
grep -q "kern.racct.enable" /boot/loader.conf || \
    echo 'kern.racct.enable=1' >> /boot/loader.conf

echo "Loading if_epair for the VNET tests."
grep -q "if_epair_load" /boot/loader.conf || \
    echo 'if_epair_load="YES"' >> /boot/loader.conf
kldload if_epair 2>/dev/null || true

echo "Creating the file-backed ZFS pool."
kldload zfs 2>/dev/null || true
sysrc zfs_enable=YES
if ! zpool list ioc-test > /dev/null 2>&1; then
    mkdir -p /pools
    truncate -s 16G /pools/ioc-test.img
    zpool create -m /.ioc-test ioc-test /pools/ioc-test.img
    zfs set compression=lz4 ioc-test
fi
zpool list ioc-test

# file-backed pools are not always reimported at boot
cat > /etc/rc.local <<'RCLOCAL'
#!/bin/sh
zpool list ioc-test > /dev/null 2>&1 || zpool import -d /pools ioc-test
RCLOCAL
chmod +x /etc/rc.local

echo "Creating the Python virtual environment."
PYBIN="$(ls /usr/local/bin/ | grep -E '^python3\.[0-9]+$' | head -n 1)"
[ -d /root/venv ] || "/usr/local/bin/${PYBIN}" -m venv \
    --system-site-packages /root/venv
/root/venv/bin/pip install -q -U pip setuptools wheel

echo "Guest setup finished."
uname -a
freebsd-version
GUEST_SCRIPT

echo "Mirroring the package cache to the host."
mkdir -p "${CACHE_DIR}/pkg-cache"
rsync -a -e "ssh ${SSH_OPTS}" \
    root@127.0.0.1:/var/cache/pkg/ "${CACHE_DIR}/pkg-cache/"

echo "Guest setup complete."
