ZPOOL=""
SERVER=""
SVN_REL_URL=https://svn.freebsd.org/base/releng/11.1

install:
	python3.6 -m ensurepip
	pkg install -q -y libgit2 libucl cython3 rsync
	( cd /usr/src && svnlite checkout $(SVN_REL_URL)/cddl/ && \
		mkdir -p sys && cd sys && svnlite checkout $(SVN_REL_URL)/sys/cddl )
	pip3.6 install -Ur requirements.txt # properly install libzfs
	pip3.6 install -e . # install libiocage from source / for testing.
uninstall:
	pip3.6 uninstall -y libiocage
test:
	pytest --zpool $(ZPOOL) --server $(SERVER)
help:
	@echo "    install"
	@echo "        Installs libiocage"
	@echo "    uninstall"
	@echo "        Removes libiocage."
	@echo "    test"
	@echo "        Run unit tests with pytest"
