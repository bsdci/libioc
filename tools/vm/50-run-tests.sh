#!/bin/sh
# Sync the repository into the guest, install it and run the test tiers.
# usage: 50-run-tests.sh [tier0|tier1|tier2|tier3|smoke] [pytest args...]
set -e
. "$(dirname "$0")/config.sh"

TIER="${1:-tier1}"
[ $# -gt 0 ] && shift

REPO_DIR="$(cd "${VM_DIR}/../.." && pwd)"

run_guest() {
    sh "${FREEBSD_CI_DIR}/scripts/run.sh" -n "$1"
}

# the shared run.sh recreates its work directory on every sync, while
# the suite's release download cache inside the guest must survive
# between runs, so the repository syncs incrementally with rsync
echo "Synchronizing the repository into the guest."
rsync -a --delete \
    --exclude=.git \
    --exclude=.venv \
    --exclude=.cache \
    --exclude=.mypy_cache \
    --exclude=.pytest_cache \
    --exclude=tools/vm/cache \
    --exclude=tools/vm/freebsd-ci \
    -e "ssh ${SSH_OPTS}" \
    "${REPO_DIR}/" root@127.0.0.1:/root/libioc/

echo "Installing libioc into the guest venv."
run_guest 'cd /root/libioc && /root/venv/bin/pip install -q -r requirements.txt -r requirements-test.txt'
run_guest 'cd /root/libioc && /root/venv/bin/pip install -q -e .'

case "${TIER}" in
    tier0)
        echo "Tier 0: full package import sweep."
        run_guest '/root/venv/bin/python /root/libioc/tools/vm/import_sweep.py'
        ;;
    tier1)
        echo "Tier 1: fast platform tests."
        run_guest "cd /root/libioc && /root/venv/bin/pytest tests/test_MacAddress.py tests/test_Fstab.py tests/test_helpers.py tests/test_ConfigData.py tests/test_Filter.py tests/test_ResourceLimit.py --zpool ioc-test -x $*"
        ;;
    tier2)
        echo "Tier 2: jail lifecycle tests (downloads the release on first run)."
        run_guest "cd /root/libioc && /root/venv/bin/pytest tests/test_Config.py tests/test_Storage.py tests/test_Jail.py --zpool ioc-test -x $*"
        ;;
    tier3)
        echo "Tier 3: full suite."
        run_guest "cd /root/libioc && /root/venv/bin/pytest tests --zpool ioc-test --junitxml=/root/libioc-results.xml $*"
        ;;
    smoke)
        echo "Smoke test: full jail lifecycle."
        run_guest '/root/venv/bin/python /root/libioc/tools/vm/smoke.py'
        ;;
    *)
        echo "usage: $0 {tier0|tier1|tier2|tier3|smoke} [pytest args]" >&2
        exit 1
        ;;
esac
