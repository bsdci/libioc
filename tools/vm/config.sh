# libioc-specific defaults on top of the shared freebsd-ci tooling.
# Every script in this directory sources this file.

VM_DIR="$(cd "$(dirname "$0")" && pwd)"
FREEBSD_CI_DIR="${VM_DIR}/freebsd-ci"

if [ ! -d "${FREEBSD_CI_DIR}" ]; then
    echo "Shared tooling missing; run tools/vm/00-bootstrap.sh first." >&2
    exit 1
fi

FREEBSD_VERSION="${FREEBSD_VERSION:-13.5-RELEASE}"
export FREEBSD_VERSION
FREEBSD_CI_CACHE="${FREEBSD_CI_CACHE:-${VM_DIR}/cache}"
export FREEBSD_CI_CACHE
IMAGES_CONF="${FREEBSD_CI_DIR}/images.conf"
export IMAGES_CONF

. "${FREEBSD_CI_DIR}/scripts/config.sh"
