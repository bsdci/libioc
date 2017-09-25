ZPOOL=""
SERVER=""
MYPYPATH = $(shell pwd)/.travis/mypy-stubs

deps:
	pkg install -q -y libucl cython3 rsync python36 py36-libzfs
	python3.6 -m ensurepip
	pip3.6 install -Ur requirements.txt
#install: deps
install:
	pip3.6 install -U --compile .
install-dev: deps
	pip3.6 install flake8-mutable flake8-builtins flake8-mypy bandit bandit-high-entropy-string
	pip3.6 install -e .
uninstall:
	pip3.6 uninstall -y iocage
check:
	flake8 --exclude=".*" --exclude=__init__.py --ignore=E203,W391
	bandit --skip B404 --exclude iocage/tests/ -r .
test:
	pytest --zpool $(ZPOOL) --server $(SERVER)
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
