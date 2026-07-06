ZPOOL?=
JAIL_NIC?=vtnet0
JAIL_IP?=172.16.0
JAIL_NET?=16

PYTHON_VERSION ?= $(TRAVIS_PYTHON_VERSION)
SELECTED_PYTHON_VERSION != if [ "$(PYTHON_VERSION)" != "" ]; then echo $(PYTHON_VERSION); else pkg query '%dn' 'python3' | sort -un | sed -r 's/^python//;s/^([0-9])([0-9]+)/\1.\2/' | tail -n1 ; fi
PYTHON ?= python${SELECTED_PYTHON_VERSION}
# turn python3.7 -> 3.7 -> 37
pyver= ${PYTHON:S/^python//:S/.//:C/\([0-9]+\)/\1/}

.if $(pyver) < 35
. error "libioc cannot run with a Python version < 3.5"
.endif

install: install-deps install-python-requirements
	$(PYTHON) -m pip install -U .
install-python-requirements:
	$(PYTHON) -m ensurepip
	$(PYTHON) -m pip install -Ur requirements.txt
install-python-requirements-dev: install-python-requirements
	$(PYTHON) -m pip install -Ur requirements-dev.txt
install-deps:
	pkg install -q -y libucl rsync git py$(pyver)-ucl py$(pyver)-libzfs
install-deps-dev: install-deps
	if [ "`uname`" = "FreeBSD" ]; then pkg install -y gmake py$(pyver)-setuptools py$(pyver)-sqlite3; fi
install-dev: install-deps-dev install-python-requirements-dev
	$(PYTHON) -m pip install -e .
uninstall:
	$(PYTHON) -m pip uninstall -y ioc
	@if [ -f /usr/local/etc/rc.d/ioc ]; then \
		rm /usr/local/etc/rc.d/ioc; \
	fi
check:
	sh scripts/check.sh
test:
	pytest tests --zpool $(ZPOOL)
.PHONY: docs
docs:
	$(PYTHON) setup.py build_sphinx
help:
	@echo "    install"
	@echo "        Installs libioc"
	@echo "    uninstall"
	@echo "        Removes libioc"
	@echo "    test"
	@echo "        Run unit tests with pytest"
	@echo "    check"
	@echo "        Run static linters & other static analysis tests"
	@echo "    install-dev"
	@echo "        Install dependencies needed to run `check`"
