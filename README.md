# libiocage

**Python Library to manage FreeBSD jails with libiocage.**

iocage is a jail/container manager fusioning some of the best features and technologies the FreeBSD operating system has to offer. It is geared for ease of use with a simple and easy to understand command syntax.

This library provides programmatic access to iocage features and jails, while aiming to be compatible with iocage-legacy, and the current Python 3 version of iocage.

### Project Status
As of November 2017 this project is *working towards an alpha release*. This means stabilization of command-line and library interfaces, so that proper integration tests can be built. This phase requires manual verification and testing until reaching feature-completion and compatibility with Python [iocage](https://github.com/iocage/iocage) and prior iocage_legacy versions with [ZFS property](https://github.com/iocage/iocage_legacy/tree/master) and [UCL file](https://github.com/iocage/iocage_legacy) config storage.

## Install

### from Master branch

```sh
git clone https://github.com/iocage/libiocage
cd libiocage
make install
```

Please note: this will build `py-libzfs` from source, which will require `/usr/src` to be populated.

## Usage

### Library

```python
import iocage

jail = iocage.Jail()
jail.create("11.1-RELEASE")
```

### CLI

Libiocage comes bundles with a CLI tool called `ioc`. It is inspired by the command line interface of [iocage](https://github.com/iocage/iocage) but meant to be developed along with the library and to spike on new features.

### Custom Release (e.g. running -CURRENT)

#### Initially create the release dataset

```sh
zfs create zroot/iocage/releases/custom/root
cd /usr/src
# install your source tree
make installworld DESTDIR=/iocage/releases/custom/root
make distribution DESTDIR=/iocage/releases/custom/root
ioc fetch -r custom -b
```

#### Update the installation after recompile
```sh
make installworld DESTDIR=/iocage/releases/custom/root
ioc fetch -r custom -b
```

## Development

### Install Development Dependencies

```sh
make install-dev
```

### Unit Tests

Unit tests may run on FreeBSD or HardenedBSD and require an activated iocage pool.

```sh
pytest
```

### Type Checking

At this time differential type checking is enabled, which allows us to incrementally cover the library with strong typings until we can switch to strict type checking.


```
make check
```

### Code Style

The code style is automatically checked with flake8.
