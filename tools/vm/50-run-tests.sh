#!/bin/sh
# Sync the repository into the guest, install it and run the test tiers.
# usage: 50-run-tests.sh [tier0|tier1|tier2|tier3|smoke] [pytest args...]
set -e
. "$(dirname "$0")/config.sh"

TIER="${1:-tier1}"
[ $# -gt 0 ] && shift

REPO_DIR="$(cd "${VM_DIR}/../.." && pwd)"

echo "Synchronizing the repository into the guest."
rsync -a --delete \
    --exclude=.git \
    --exclude=.venv \
    --exclude=.mypy_cache \
    --exclude=.pytest_cache \
    --exclude=tools/vm/cache \
    -e "ssh ${SSH_OPTS}" \
    "${REPO_DIR}/" root@127.0.0.1:/root/libioc/

echo "Installing libioc into the guest venv."
${VM_SSH} 'cd /root/libioc && /root/venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>/dev/null || /root/venv/bin/pip install -q --no-build-isolation -r requirements.txt -r requirements-dev.txt'
${VM_SSH} 'cd /root/libioc && /root/venv/bin/pip install -q --no-build-isolation -e .'

case "${TIER}" in
    tier0)
        echo "Tier 0: full package import sweep."
        ${VM_SSH} "/root/venv/bin/python -c \"
import importlib
import pkgutil
import libioc
failed = []
for module in pkgutil.walk_packages(libioc.__path__, 'libioc.'):
    try:
        importlib.import_module(module.name)
    except Exception as e:
        failed.append((module.name, repr(e)))
for name, error in failed:
    print(f'FAILED {name}: {error}')
print(f'{len(failed)} import failures')
exit(len(failed) > 0)
\""
        ;;
    tier1)
        echo "Tier 1: fast platform tests."
        ${VM_SSH} "cd /root/libioc && /root/venv/bin/pytest tests/test_MacAddress.py tests/test_Fstab.py tests/test_helpers.py tests/test_ConfigData.py tests/test_Filter.py tests/test_ResourceLimit.py --zpool ioc-test -x $*"
        ;;
    tier2)
        echo "Tier 2: jail lifecycle tests (downloads the release on first run)."
        ${VM_SSH} "cd /root/libioc && /root/venv/bin/pytest tests/test_Config.py tests/test_Storage.py tests/test_Jail.py --zpool ioc-test -x $*"
        ;;
    tier3)
        echo "Tier 3: full suite."
        ${VM_SSH} "cd /root/libioc && /root/venv/bin/pytest tests --zpool ioc-test --junitxml=/root/libioc-results.xml $*"
        ;;
    smoke)
        echo "Smoke test: full jail lifecycle."
        ${VM_SSH} '/root/venv/bin/python /root/libioc/tools/vm/smoke.py'
        ;;
    *)
        echo "usage: $0 {tier0|tier1|tier2|tier3|smoke} [pytest args]" >&2
        exit 1
        ;;
esac
