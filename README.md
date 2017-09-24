# libiocage

[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/iocage/libiocage.svg)](http://isitmaintained.com/project/iocage/libiocage "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/iocage/libiocage.svg)](http://isitmaintained.com/project/iocage/libiocage "Percentage of issues still open")
![Python Version](https://img.shields.io/badge/Python-3.6-blue.svg)
[![GitHub issues](https://img.shields.io/github/issues/iocage/libiocage.svg)](https://github.com/iocage/libiocage/issues)
[![GitHub forks](https://img.shields.io/github/forks/iocage/libiocage.svg)](https://github.com/iocage/libiocage/network)
[![GitHub stars](https://img.shields.io/github/stars/iocage/libiocage.svg)](https://github.com/iocage/libiocage/stargazers)
[![Twitter](https://img.shields.io/twitter/url/https/github.com/iocage/libiocage.svg?style=social)](https://twitter.com/intent/tweet?text=@iocage)

**Python Library to manage FreeBSD jails with libiocage.**

iocage is a jail/container manager amalgamating some of the best features and technologies the FreeBSD operating system has to offer. It is geared for ease of use with a simple and easy to understand command syntax.

This library provides programmatic access to iocage features and jails, while being compatible with iocage-legacy, and the current Python 3 version of iocage.

## Install

### from Source Distribution

```sh
pkg install python36 py36-pygit2 py36-libzfs libucl
python3.6 -m ensurepip
pip3.6 install iocage
```

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

#### Initially create release dataset

```sh
zfs create zroot/iocage/releases/custom/root
cd /usr/src
#install your source tree
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
setenv MYPYPATH `pwd`/.travis/mypy-stubs
mypy iocage/
```

### Code Style

The code style is automatically checked with flake8.
