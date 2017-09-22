ZPOOL=""
SERVER=""

install:
	pkg install -q -y libucl cython3 rsync python36 py36-libzfs
	python3.6 -m ensurepip
	pip3.6 install -Ur requirements.txt
	pip3.6 install -e .
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
