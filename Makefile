ZPOOL=""
SERVER=""

install:
	python3.6 -m ensurepip
	pkg install -q -y libgit2 libucl cython3
	pip3.6 install -U .
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
