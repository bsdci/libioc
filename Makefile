ZPOOL?=
JAIL_NIC?=vtnet0
JAIL_IP?=172.16.0
JAIL_NET?=16
MYPYPATH = $(shell pwd)/.travis/mypy-stubs

PYTHON_VERSION ?= $(TRAVIS_PYTHON_VERSION)
SELECTED_PYTHON_VERSION != if [ "$(PYTHON_VERSION)" != "" ]; then echo $(PYTHON_VERSION); else pkg query '%dn' 'python3' | sort -un | sed -r 's/^python//;s/^([0-9])([0-9]+)/\1.\2/' | tail -n1 ; fi
PYTHON ?= python${SELECTED_PYTHON_VERSION}
# turn python3.7 -> 3.7 -> 37
pyver= ${PYTHON:S/^python//:S/.//:C/\([0-9]+\)/\1/}

.if $(pyver) < 35
. error "libioc cannot run with a Python version < 3.5"
.endif

install:
	$(PYTHON) setup.py install
install-travis:
	python$(TRAVIS_PYTHON_VERSION) -m pip install -IU flake8-mutable flake8-docstrings flake8-builtins flake8-mypy bandit==1.5.1 bandit-high-entropy-string
check:
	flake8 --version
	mypy --version
	flake8 --exclude=".travis,.eggs,__init__.py,docs,tests" --ignore=E203,E252,W391,D107,A001,A002,A003,A004,D412,D413,T499
	bandit --skip B404,B110 --exclude tests/ -r .
test:
	pytest tests --zpool $(ZPOOL)
.PHONY: docs
docs:
	$(PYTHON) setup.py build_sphinx
help:
	@echo "    install"
	@echo "        Installs libioc"
	@echo "    test"
	@echo "        Run unit tests with pytest"
	@echo "    check"
	@echo "        Run static linters & other static analysis tests"
	@echo "    docs"
	@echo "        Generate documentation"
