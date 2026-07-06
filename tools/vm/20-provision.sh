#!/bin/sh
# First-boot provisioning of the FreeBSD VM.
#
# The official VM images boot with the video console, and the serial
# port stays silent until the kernel console is switched, so the script
# drives the VGA console blindly through the QEMU monitor: it waits for
# the boot to settle, logs in as root (no password on the official
# images), enables sshd, installs the SSH key and makes the serial
# console permanent for all future boots.
set -e
. "$(dirname "$0")/config.sh"

if [ ! -f "${SSH_KEY}.pub" ]; then
    echo "SSH key missing; run 00-host-setup.sh first." >&2
    exit 1
fi

MONITOR_SOCKET="${CACHE_DIR}/mon.sock"
PYTHON="${PYTHON:-python3}"

if [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo "VM is already running; provisioning expects a fresh boot." >&2
    exit 1
fi

qemu-system-x86_64 \
    -machine pc -accel tcg,thread=multi -cpu max \
    -smp "${VM_CPUS}" -m "${VM_MEMORY_MB}" \
    -display none -vga std \
    -monitor "unix:${MONITOR_SOCKET},server,nowait" \
    -serial "unix:${SERIAL_SOCKET},server,nowait" \
    -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22" \
    -device virtio-net-pci,netdev=n0 \
    -drive "if=virtio,file=${WORK_IMAGE},format=qcow2" \
    -rtc base=utc \
    -daemonize -pidfile "${PID_FILE}"

echo "Waiting for the guest to boot."
sleep 120

type_line() {
    "${PYTHON}" "${VM_DIR}/monitor_type.py" "${MONITOR_SOCKET}" \
        typeline "$1"
    sleep "${2:-2}"
}

PUBKEY="$(awk '{print $1" "$2}' "${SSH_KEY}.pub")"

echo "Typing the provisioning commands into the VGA console."
type_line "root" 5
type_line "printf 'console=\"comconsole\"\\n' >> /boot/loader.conf"
type_line "sysrc sshd_enable=YES" 4
type_line "printf 'PermitRootLogin without-password\\n' >> /etc/ssh/sshd_config"
type_line "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
type_line "echo '${PUBKEY}' > /root/.ssh/authorized_keys" 3
type_line "chmod 600 /root/.ssh/authorized_keys"
type_line "service sshd start" 8

echo "Testing SSH access."
i=0
while [ "$i" -lt 12 ]; do
    if ${VM_SSH} -o ConnectTimeout=5 'echo provisioned' 2>/dev/null; then
        echo "Provisioning finished; the VM stays running."
        exit 0
    fi
    i=$((i + 1))
    sleep 10
done

echo "SSH did not come up; inspect the console with a screendump:" >&2
echo "  ${PYTHON} ${VM_DIR}/monitor_type.py ${MONITOR_SOCKET} screendump /tmp/screen.png" >&2
exit 1
