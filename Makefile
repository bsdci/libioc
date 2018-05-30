ZPOOL?=
JAIL_NIC?=vtnet0
JAIL_IP?=172.16.0
JAIL_NET?=16
MYPYPATH = $(shell pwd)/.travis/mypy-stubs

deps:
	which pkg && pkg install -q -y libucl py36-cython rsync python36 py36-libzfs py36-sysctl || true
	python3.6 -m ensurepip
	python3.6 -m pip install -Ur requirements.txt
install: deps
	python3.6 -m pip install -U .
	@if [ -f /usr/local/etc/init.d ]; then \
		install -m 0755 rc.d/ioc /usr/local/etc/init.d; \
	else \
		install -m 0755 rc.d/ioc /usr/local/etc/rc.d; \
	fi
install-dev: deps
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
	python3.6 -m pip uninstall -y iocage
check:
	flake8 --version
	flake8 --exclude=".travis,.eggs,__init__.py" --ignore=E203,W391,D107,A001,A002,A003,A004
	bandit --skip B404 --exclude iocage/tests/ -r .
test:
	pytest iocage/tests --zpool $(ZPOOL)
regression-test:
	iocage/tests/run-integration.sh

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
