ZPOOL?=
JAIL_NIC?=vtnet0
JAIL_IP?=172.16.0
JAIL_NET?=16
MYPYPATH = $(shell pwd)/.travis/mypy-stubs

deps:
	if [ "`uname`" = "FreeBSD" ]; then pkg install -q -y libucl py36-cython rsync python36 py36-libzfs py36-sysctl; fi
	python3.6 -m ensurepip
	python3.6 -m pip install -Ur requirements.txt
	python3.6 -m pip install -Ur requirements-ioc.txt
install: deps
	python3.6 -m pip install -U .
	@if [ -f /usr/local/etc/init.d ]; then \
		install -m 0755 rc.d/ioc /usr/local/etc/init.d; \
	else \
		install -m 0755 rc.d/ioc /usr/local/etc/rc.d; \
	fi
install-dev: deps
	if [ "`uname`" = "FreeBSD" ]; then pkg install -y gmake; fi
	python3.6 -m pip install -Ur requirements-dev.txt
	python3.6 -m pip install -e .
	@if [ -f /usr/local/etc/init.d ]; then \
		install -m 0755 -o root -g wheel rc.d/ioc /usr/local/etc/init.d; \
	else \
		install -m 0755 -o root -g wheel rc.d/ioc /usr/local/etc/rc.d; \
	fi
install-travis:
	python3.6 -m pip install flake8-mutable flake8-docstrings flake8-builtins flake8-mypy bandit bandit-high-entropy-string
uninstall:
	python3.6 -m pip uninstall -y iocage ioc
	@if [ -f /usr/local/etc/rc.d/ioc ]; then \
		rm /usr/local/etc/rc.d/ioc; \
	fi
check:
	flake8 --version
	flake8 --exclude=".travis,.eggs,__init__.py,docs" --ignore=E203,E252,W391,D107,A001,A002,A003,A004
	bandit --skip B404 --exclude tests/ -r .
test:
	pytest tests --zpool $(ZPOOL)
regression-test:
	tests/run-integration.sh
.PHONY: docs
docs:
	sphinx-apidoc -o docs --separate -H libiocage -A "iocage Authors" --full iocage ioc tests
	if [ "`uname`" = "FreeBSD" ]; then gmake -C docs html; else make -C docs html; fi

help:
	@echo "    install"
	@echo "        Installs libiocage"
	@echo "    uninstall"
	@echo "        Removes libiocage."
	@echo "    test"
	@echo "        Run unit tests with pytest"
	@echo "    check"
	@echo "        Run static linters & other static analysis tests"
	@echo "    install-dev"
	@echo "        Install dependencies needed to run `check`"
