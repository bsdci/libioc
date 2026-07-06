#!/bin/sh
# Download the FreeBSD BASIC-CI image from the archive server, verify
# its checksum and prepare the copy-on-write work image.
set -e
. "$(dirname "$0")/config.sh"

mkdir -p "${CACHE_DIR}"
cd "${CACHE_DIR}"

if [ ! -f "${IMAGE_ARCHIVE}" ]; then
    echo "Downloading ${IMAGE_URL}"
    curl -sS --retry 3 -C - -o "${IMAGE_ARCHIVE}" "${IMAGE_URL}"
fi

echo "${IMAGE_SHA256}  ${IMAGE_ARCHIVE}" | sha256sum -c -

if [ ! -f "${BASE_IMAGE}" ]; then
    echo "Unpacking and converting ${IMAGE_ARCHIVE}"
    unxz -k "${IMAGE_ARCHIVE}"
    qemu-img convert -f raw -O qcow2 "${IMAGE_NAME}" "${BASE_IMAGE}"
    rm "${IMAGE_NAME}"
fi

if [ ! -f "${WORK_IMAGE}" ]; then
    qemu-img create -f qcow2 -F qcow2 \
        -b "${BASE_IMAGE}" "${WORK_IMAGE}" "${WORK_IMAGE_SIZE}"
    echo "Created ${WORK_IMAGE} (${WORK_IMAGE_SIZE})"
fi

echo "Image ready: ${WORK_IMAGE}"
