ZPOOL?=
JAIL_NIC?=vtnet0
JAIL_IP?=172.16.0
JAIL_NET?=16
MYPYPATH = $(shell pwd)/.travis/mypy-stubs
PYTHON ?= python3.6

pyver= ${PYTHON:S/^python//:S/.//:C/\([0-9]+\)/\1/}

.if $(pyver) < 35
. error "libioc cannot run with a Python version < 3.5"
.endif

deps:
	pkg install -q -y libucl py$(pyver)-cython rsync python$(pyver) py$(pyver)-libzfs
	$(PYTHON) -m ensurepip
	$(PYTHON) -m pip install -Ur requirements.txt
install: deps
	$(PYTHON) -m pip install -U .
	@if [ -f /usr/local/etc/init.d ]; then \
		install -m 0755 rc.d/ioc /usr/local/etc/init.d; \
	else \
		install -m 0755 rc.d/ioc /usr/local/etc/rc.d; \
	fi
install-dev: deps
	if [[ "`uname`" = "FreeBSD" ]]; then pkg install -y gmake py36-sqlite3; fi
	$(PYTHON) -m pip install -Ur requirements-dev.txt
	$(PYTHON) -m pip install -e .
install-travis:
	$(PYTHON) -m pip install flake8-mutable flake8-docstrings flake8-builtins flake8-mypy bandit bandit-high-entropy-string
uninstall:
	$(PYTHON) -m pip uninstall -y ioc
	@if [ -f /usr/local/etc/rc.d/ioc ]; then \
		rm /usr/local/etc/rc.d/ioc; \
	fi
check:
	flake8 --version
	flake8 --exclude=".travis,.eggs,__init__.py,docs" --ignore=E203,E252,W391,D107,A001,A002,A003,A004
	bandit --skip B404,B110 --exclude tests/ -r .
test:
	pytest tests --zpool $(ZPOOL)
regression-test:
	tests/run-integration.sh
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
