#!/bin/sh
# Install the host packages and fetch the shared FreeBSD CI tooling.
# The generic VM plumbing lives in the freebsd-ci repository and is
# pinned here; only the libioc-specific setup stays in this directory.
set -e
VM_DIR="$(cd "$(dirname "$0")" && pwd)"

FREEBSD_CI_REPO="https://github.com/gronke/freebsd-ci.git"
FREEBSD_CI_REF="ee9770828ffa9dc1e58641874b5ec020b11a14e9"

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    qemu-system-x86 qemu-utils sshpass xz-utils rsync openssh-client

if [ ! -d "${VM_DIR}/freebsd-ci/.git" ]; then
    git clone -q "${FREEBSD_CI_REPO}" "${VM_DIR}/freebsd-ci"
fi
git -C "${VM_DIR}/freebsd-ci" remote set-url origin "${FREEBSD_CI_REPO}"
git -C "${VM_DIR}/freebsd-ci" fetch -q origin
git -C "${VM_DIR}/freebsd-ci" checkout -q "${FREEBSD_CI_REF}"

echo "Bootstrap complete; freebsd-ci at ${FREEBSD_CI_REF}."
