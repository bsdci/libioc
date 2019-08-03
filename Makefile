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

install: install-deps install-python-requirements
	$(PYTHON) -m pip install -U .
install-python-requirements:
	$(PYTHON) -m ensurepip
	$(PYTHON) -m pip install -Ur requirements.txt
install-python-requirements-dev: install-python-requirements
	$(PYTHON) -m pip install -Ur requirements-dev.txt
install-deps:
	pkg install -q -y libucl py$(pyver)-ucl py$(pyver)-cython rsync python$(pyver) py$(pyver)-libzfs
install-deps-dev: install-deps
	if [ "`uname`" = "FreeBSD" ]; then pkg install -y gmake py36-sqlite3; fi
install-dev: install-deps-dev install-python-requirements-dev
	$(PYTHON) -m pip install -e .
install-travis:
	python3.6 -m pip install -IU flake8-mutable flake8-docstrings flake8-builtins flake8-mypy bandit==1.5.1 bandit-high-entropy-string
uninstall:
	$(PYTHON) -m pip uninstall -y ioc
	@if [ -f /usr/local/etc/rc.d/ioc ]; then \
		rm /usr/local/etc/rc.d/ioc; \
	fi
check:
	flake8 --version
	flake8 --exclude=".travis,.eggs,__init__.py,docs,tests" --ignore=E203,E252,W391,D107,A001,A002,A003,A004,D412,D413
	bandit --skip B404,B110 --exclude tests/ -r .
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
