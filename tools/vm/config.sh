# Shared configuration of the FreeBSD test VM scripts.
# Every script in this directory sources this file.

VM_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="${VM_DIR}/cache"

FREEBSD_VERSION="13.5-RELEASE"
IMAGE_NAME="FreeBSD-${FREEBSD_VERSION}-amd64.qcow2"
IMAGE_ARCHIVE="${IMAGE_NAME}.xz"
IMAGE_URL="http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/VM-IMAGES/${FREEBSD_VERSION}/amd64/Latest/${IMAGE_ARCHIVE}"
# ftp-archive.freebsd.org only serves plain HTTP, so the download is
# verified against this pinned checksum of the xz archive.
IMAGE_SHA256="6de6d33be8ec72847aca7e5bf3c3d4f9b2b9861ab4bb75b51e33a0655e15253f"

BASE_IMAGE="${CACHE_DIR}/${IMAGE_NAME}"
WORK_IMAGE="${CACHE_DIR}/work.qcow2"
WORK_IMAGE_SIZE="40G"

VM_MEMORY_MB="8192"
VM_CPUS="8"
SSH_PORT="2222"
SSH_KEY="${CACHE_DIR}/id_ed25519"
PID_FILE="${CACHE_DIR}/qemu.pid"
SERIAL_SOCKET="${CACHE_DIR}/serial.sock"

SSH_OPTS="-p ${SSH_PORT} -i ${SSH_KEY} \
    -o UserKnownHostsFile=${CACHE_DIR}/known_hosts \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=15"
VM_SSH="ssh ${SSH_OPTS} root@127.0.0.1"
