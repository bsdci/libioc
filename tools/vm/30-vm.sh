#!/bin/sh
# Control the FreeBSD test VM: up, down, status, ssh, console.
set -e
. "$(dirname "$0")/config.sh"

qemu_running() {
    [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null
}

case "${1:-}" in
    up)
        if qemu_running; then
            echo "VM is already running (pid $(cat "${PID_FILE}"))."
            exit 0
        fi
        qemu-system-x86_64 \
            -machine pc -accel tcg,thread=multi -cpu max \
            -smp "${VM_CPUS}" -m "${VM_MEMORY_MB}" \
            -display none -vga std \
            -monitor "unix:${CACHE_DIR}/mon.sock,server,nowait" \
            -serial "unix:${SERIAL_SOCKET},server,nowait" \
            -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22" \
            -device virtio-net-pci,netdev=n0 \
            -drive "if=virtio,file=${WORK_IMAGE},format=qcow2" \
            -rtc base=utc \
            -daemonize -pidfile "${PID_FILE}"
        echo "VM starting; waiting for SSH on port ${SSH_PORT}."
        i=0
        while [ "$i" -lt 120 ]; do
            if ${VM_SSH} -o ConnectTimeout=5 true 2>/dev/null; then
                echo "VM is up."
                exit 0
            fi
            i=$((i + 1))
            sleep 5
        done
        echo "VM did not become reachable within 10 minutes." >&2
        exit 1
        ;;
    down)
        if qemu_running; then
            ${VM_SSH} 'shutdown -p now' 2>/dev/null || true
            i=0
            while qemu_running && [ "$i" -lt 36 ]; do
                i=$((i + 1))
                sleep 5
            done
            if qemu_running; then
                echo "Graceful shutdown timed out, killing QEMU." >&2
                kill "$(cat "${PID_FILE}")"
            fi
        fi
        rm -f "${PID_FILE}"
        echo "VM is down."
        ;;
    status)
        if qemu_running; then
            echo "VM is running (pid $(cat "${PID_FILE}"))."
        else
            echo "VM is not running."
        fi
        ;;
    ssh)
        shift
        exec ${VM_SSH} "$@"
        ;;
    console)
        echo "Connecting to serial console (exit with Ctrl-C)."
        exec socat "UNIX-CONNECT:${SERIAL_SOCKET}" STDIO
        ;;
    *)
        echo "usage: $0 {up|down|status|ssh [command]|console}" >&2
        exit 1
        ;;
esac
