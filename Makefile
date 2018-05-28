ZPOOL?=
JAIL_NETNIC?=vtnet0
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
regressions: install
	# can be activated
	ioc activate $(ZPOOL)
	ioc deactivate $(ZPOOL)
	# can be activated with special mount-point
	ioc activate $(ZPOOL)  --mountpoint /$(ZPOOL)/iocage-tests
	mount | grep -q "$(ZPOOL)/iocage on /$(ZPOOL)/iocage-tests"
	# fetch default release:
	yes "" | ioc fetch
	ioc list --release --no-header --output-format=list | grep -q 11.1-RELEASE
	# fetch older release:
	ioc fetch --release 10.4-RELEASE
	ioc list --release --no-header --output-format=list | grep -q 10.4-RELEASE

	# create a template
	ioc create --basejail --name tpl-web ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).2/$(JAIL_NET)"
	ioc start tpl-web
	ioc exec tpl-web env ASSUME_ALWAYS_YES=YES pkg bootstrap
	ioc exec tpl-web env ASSUME_ALWAYS_YES=YES pkg install -y apache24
	ioc stop tpl-web
	ioc set template=yes tpl-web

	# template from 10.4-RELEASE
	ioc create --basejail --name tpl-db --release 10.4-RELEASE ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).3/$(JAIL_NET)"
	ioc start tpl-db
	ioc exec tpl-db env ASSUME_ALWAYS_YES=YES pkg bootstrap
	ioc exec tpl-db env ASSUME_ALWAYS_YES=YES pkg install -y mysql57-server
	ioc stop tpl-db
	ioc set template=yes tpl-db

	ioc create --basejail --template tpl-db --name db01 boot=yes ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).4/$(JAIL_NET)"
	ioc create --basejail --template tpl-db --name db02 boot=yes ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).5/$(JAIL_NET)"
	ioc start 'db0*'
	ioc list --no-header --output-format=list | grep -c db0 | grep -qw 2

	ioc create --basejail --template tpl-web --name web01 ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).6/$(JAIL_NET)"
	ioc create --basejail --template tpl-web --name web02 ip4_addr="$(JAIL_NETNIC)|$(JAIL_IP).7/$(JAIL_NET)"
	ioc start 'web0*'
	ioc list --no-header --output-format=list | grep -c web0 | grep -qw 2

	# stop all
	ioc stop '*'

	# cleanup
	ioc destroy --force '*01'
	yes | ioc destroy '*02'
	ioc destroy --force template=yes

	# cleanup
	yes | ioc destroy --release 10.4-RELEASE
	ioc destroy --force --release 11.1-RELEASE
	ioc deactivate $(ZPOOL)


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
