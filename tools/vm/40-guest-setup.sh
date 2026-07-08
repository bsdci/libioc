#!/bin/sh
# Prepare the FreeBSD guest for running the libioc test suite.
# The generic preparation steps come from the shared guest helpers;
# only the libioc package set, pool, venv and cache handling live here.
# The script is idempotent.
set -e
. "$(dirname "$0")/config.sh"

GUEST="${FREEBSD_CI_DIR}/scripts/guest.sh"
RUN="${FREEBSD_CI_DIR}/scripts/run.sh"

echo "Synchronizing the guest clock."
sh "${RUN}" -n 'service ntpd onestop 2>/dev/null || true
ntpdate -b 0.freebsd.pool.ntp.org || ntpdate -b pool.ntp.org || true'

echo "Installing packages."
sh "${GUEST}" pkg-repo latest
sh "${GUEST}" pkg-install pkg > /dev/null
PYPKG="$(sh "${RUN}" -n \
    "pkg search -q '^py3[0-9]*-libzfs' | head -n 1 | sed 's/-libzfs.*//'")"
if [ -z "${PYPKG}" ]; then
    echo "Could not detect the python package prefix." >&2
    exit 1
fi
echo "Python package prefix: ${PYPKG}"
sh "${GUEST}" pkg-install python3 \
    "${PYPKG}-libzfs" "${PYPKG}-ucl" "${PYPKG}-sqlite3" \
    "${PYPKG}-setuptools" "${PYPKG}-pip" git rsync

echo "Preparing the system."
sh "${GUEST}" fdescfs
sh "${GUEST}" kld if_epair fusefs
sh "${GUEST}" zpool ioc-test 16G

echo "Creating the Python virtual environment."
sh "${RUN}" -n 'PYBIN="$(ls /usr/local/bin/ | grep -E "^python3\.[0-9]+$" | head -n 1)"
[ -d /root/venv ] || "/usr/local/bin/${PYBIN}" -m venv --system-site-packages /root/venv
/root/venv/bin/pip install -q -U pip setuptools wheel'

echo "Mirroring the package cache to the host."
sh "${GUEST}" mirror-pkg-cache "${CACHE_DIR}/pkg-cache"

echo "Enabling resource accounting (reboots once when not active)."
sh "${GUEST}" tunable kern.racct.enable=1

echo "Guest setup complete."
sh "${RUN}" -n 'uname -a && freebsd-version'
