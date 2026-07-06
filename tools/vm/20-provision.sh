#!/bin/sh
# First-boot provisioning of the FreeBSD BASIC-CI VM over SSH.
#
# The BASIC-CI image boots with a serial console, DHCP, growfs and an
# sshd that accepts root with an empty password.
# The script waits for SSH, installs the SSH key and closes the
# empty-password access again.
# The SSH port is only forwarded on 127.0.0.1.
set -e
. "$(dirname "$0")/config.sh"

if [ ! -f "${SSH_KEY}.pub" ]; then
    echo "SSH key missing; run 00-host-setup.sh first." >&2
    exit 1
fi

if [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo "VM is already running; provisioning expects a fresh boot." >&2
    exit 1
fi

# a freshly provisioned image has new host keys
rm -f "${CACHE_DIR}/known_hosts"

start_qemu

# while the root password is empty, sshd accepts the initial none
# authentication for every client, so completed provisioning can only
# be detected by the guest state, not by the authentication method
KEY_SSH="${VM_SSH} -o BatchMode=yes"
PASSWORD_SSH="sshpass -p \"\" ssh -p ${SSH_PORT} \
    -o UserKnownHostsFile=${CACHE_DIR}/known_hosts \
    -o StrictHostKeyChecking=accept-new \
    -o PubkeyAuthentication=no \
    -o ConnectTimeout=5"

PUBKEY="$(cat "${SSH_KEY}.pub")"

# the first boot under TCG emulation takes several minutes on busy
# hosts, plus one automatic reboot after growing the filesystem
echo "Waiting for SSH on port ${SSH_PORT}."
i=0
while [ "$i" -lt 120 ]; do
    if ${KEY_SSH} -o ConnectTimeout=5 \
            "grep -qF '${PUBKEY}' /root/.ssh/authorized_keys" \
            2>/dev/null; then
        echo "Provisioning finished earlier; the VM is up."
        exit 0
    fi
    # gate on the firstboot marker so provisioning does not race the
    # automatic reboot after growing the root filesystem
    if ${PASSWORD_SSH} root@127.0.0.1 \
            'test ! -e /firstboot' 2>/dev/null; then
        break
    fi
    i=$((i + 1))
    sleep 10
done
if [ "$i" -ge 120 ]; then
    echo "SSH did not come up; last serial console output:" >&2
    tail -n 50 "${SERIAL_LOG}" >&2 || true
    exit 1
fi

echo "Installing the SSH key and closing empty-password access."
printf '%s\n' \
    "mkdir -p /root/.ssh && chmod 700 /root/.ssh" \
    "echo '${PUBKEY}' > /root/.ssh/authorized_keys" \
    "chmod 600 /root/.ssh/authorized_keys" \
    "sed -i '' -e 's/^PermitEmptyPasswords.*/PermitEmptyPasswords no/' -e 's/^PasswordAuthentication.*/PasswordAuthentication no/' -e 's/^PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config" \
    "service sshd restart" \
    | ${PASSWORD_SSH} root@127.0.0.1 sh -s

# the image reboots itself once after growing the root filesystem on
# the first boot, so the verification waits through that reboot;
# grep runs without -q because closing the pipe early kills sshd -T
# with SIGPIPE, which the remote shell reports as a failure
echo "Verifying key-based access."
i=0
while [ "$i" -lt 36 ]; do
    if ${KEY_SSH} -o ConnectTimeout=5 \
            'sshd -T | grep permitemptypasswords' \
            2>/dev/null | grep -q "permitemptypasswords no"; then
        echo "Provisioning finished; the VM stays running."
        exit 0
    fi
    i=$((i + 1))
    sleep 10
done
echo "Key-based SSH login did not work after provisioning." >&2
exit 1
