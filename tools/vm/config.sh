# Shared configuration of the FreeBSD test VM scripts.
# Every script in this directory sources this file.

VM_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="${VM_DIR}/cache"

# The BASIC-CI image ships with a serial console, sshd that accepts
# root with an empty password on first boot, DHCP and growfs, so it
# can be provisioned over SSH without console interaction.
FREEBSD_VERSION="13.5-RELEASE"
IMAGE_NAME="FreeBSD-${FREEBSD_VERSION}-amd64-BASIC-CI.raw"
IMAGE_ARCHIVE="${IMAGE_NAME}.xz"
IMAGE_URL="http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/CI-IMAGES/${FREEBSD_VERSION}/amd64/Latest/${IMAGE_ARCHIVE}"
# ftp-archive.freebsd.org only serves plain HTTP, so the download is
# verified against this pinned checksum of the xz archive.
IMAGE_SHA256="d4afe69038775034e32dd87fb24211362dde41c009bc888b065fc55855e65d0d"

BASE_IMAGE="${CACHE_DIR}/FreeBSD-${FREEBSD_VERSION}-amd64-BASIC-CI.qcow2"
WORK_IMAGE="${CACHE_DIR}/work.qcow2"
WORK_IMAGE_SIZE="40G"

VM_MEMORY_MB="8192"
VM_CPUS="8"
SSH_PORT="2222"
SSH_KEY="${CACHE_DIR}/id_ed25519"
PID_FILE="${CACHE_DIR}/qemu.pid"
SERIAL_SOCKET="${CACHE_DIR}/serial.sock"
SERIAL_LOG="${CACHE_DIR}/serial.log"
MONITOR_SOCKET="${CACHE_DIR}/mon.sock"

SSH_OPTS="-p ${SSH_PORT} -i ${SSH_KEY} \
    -o UserKnownHostsFile=${CACHE_DIR}/known_hosts \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=15"
VM_SSH="ssh ${SSH_OPTS} root@127.0.0.1"

qemu_accel() {
    # KVM when the device is usable, TCG emulation otherwise
    if [ -w /dev/kvm ]; then
        echo "kvm -cpu host"
    else
        echo "tcg,thread=multi -cpu max"
    fi
}

start_qemu() {
    # the serial console stays interactive through the unix socket
    # and is mirrored into a logfile for headless debugging
    qemu-system-x86_64 \
        -machine pc -accel $(qemu_accel) \
        -smp "${VM_CPUS}" -m "${VM_MEMORY_MB}" \
        -display none -vga std \
        -monitor "unix:${MONITOR_SOCKET},server,nowait" \
        -chardev "socket,id=serial0,path=${SERIAL_SOCKET},server=on,wait=off,logfile=${SERIAL_LOG}" \
        -serial chardev:serial0 \
        -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22" \
        -device virtio-net-pci,netdev=n0 \
        -drive "if=virtio,file=${WORK_IMAGE},format=qcow2" \
        -rtc base=utc \
        -daemonize -pidfile "${PID_FILE}"
}
