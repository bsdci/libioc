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
pip3.6 install libiocage
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
import libiocage

jail = libiocage.Jail()
jail.create("11.1-RELEASE")
```

### CLI

Libiocage comes bundles with a CLI tool called `ioc`. It is inspired by the command line interface of [iocage](https://github.com/iocage/iocage) but meant to be developed along with the library and to spike on new features.
