#!/bin/sh
# Prepare the FreeBSD guest for running the libioc test suite.
# The script is idempotent and runs all steps over SSH.
set -e
. "$(dirname "$0")/config.sh"

echo "Synchronizing the guest clock."
${VM_SSH} 'service ntpd stop 2>/dev/null || true; ntpdate -b 0.freebsd.pool.ntp.org || ntpdate -b pool.ntp.org || true'

echo "Configuring the package repository."
${VM_SSH} 'mkdir -p /usr/local/etc/pkg/repos && printf "FreeBSD: { url: \"pkg+https://pkg.FreeBSD.org/\${ABI}/latest\" }\n" > /usr/local/etc/pkg/repos/FreeBSD.conf'

echo "Bootstrapping pkg and installing packages."
${VM_SSH} 'env ASSUME_ALWAYS_YES=yes pkg bootstrap -f && pkg update -f'
PYPKG="$(${VM_SSH} "pkg search -q '^py3[0-9]*-libzfs' | head -n1 | sed 's/-libzfs.*//'")"
if [ -z "${PYPKG}" ]; then
    echo "Could not detect the python package prefix." >&2
    exit 1
fi
echo "Python package prefix: ${PYPKG}"
${VM_SSH} "pkg install -y python3 ${PYPKG} ${PYPKG}-libzfs ${PYPKG}-ucl ${PYPKG}-sqlite3 ${PYPKG}-setuptools ${PYPKG}-pip git rsync ca_root_nss"

echo "Mounting fdescfs."
${VM_SSH} 'grep -q fdescfs /etc/fstab || echo "fdesc /dev/fd fdescfs rw 0 0" >> /etc/fstab; mount | grep -q "/dev/fd" || mount -t fdescfs null /dev/fd'

echo "Creating the file-backed ZFS pool."
${VM_SSH} 'kldload zfs 2>/dev/null || true; sysrc zfs_enable=YES; if ! zpool list ioc-test >/dev/null 2>&1; then mkdir -p /pools && truncate -s 16G /pools/ioc-test.img && zpool create -m /.ioc-test ioc-test /pools/ioc-test.img && zfs set compression=lz4 ioc-test; fi; zpool list ioc-test'

echo "Creating the Python virtual environment."
PYBIN="$(${VM_SSH} "ls /usr/local/bin/ | grep -E '^python3\.[0-9]+$' | head -n1")"
${VM_SSH} "[ -d /root/venv ] || ${PYBIN} -m venv --system-site-packages /root/venv"
${VM_SSH} '/root/venv/bin/pip install -q -U pip setuptools wheel'

echo "Mirroring the package cache to the host."
mkdir -p "${CACHE_DIR}/pkg-cache"
rsync -a -e "ssh ${SSH_OPTS}" root@127.0.0.1:/var/cache/pkg/ "${CACHE_DIR}/pkg-cache/"

echo "Guest setup complete."
${VM_SSH} 'uname -a && freebsd-version && zpool list'
