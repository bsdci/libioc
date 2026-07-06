#!/bin/sh
# Install the host packages required to run the FreeBSD test VM and
# generate the SSH key that the provisioning scripts use.
set -e
. "$(dirname "$0")/config.sh"

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    qemu-system-x86 qemu-utils sshpass xz-utils rsync openssh-client

mkdir -p "${CACHE_DIR}"

if [ ! -f "${SSH_KEY}" ]; then
    ssh-keygen -t ed25519 -N "" -C "libioc-test-vm" -f "${SSH_KEY}"
fi

echo "Host setup complete."
