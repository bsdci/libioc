libiocage
=========

[![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/iocage/liblibiocage.svg)](http://isitmaintained.com/project/iocage/libiocage "Average time to resolve an issue")
[![Percentage of issues still open](http://isitmaintained.com/badge/open/iocage/liblibiocage.svg)](http://isitmaintained.com/project/iocage/libiocage "Percentage of issues still open")
![Python Version](https://img.shields.io/badge/Python-3.6-blue.svg)
[![GitHub issues](https://img.shields.io/github/issues/iocage/liblibiocage.svg)](https://github.com/iocage/libiocage/issues)
[![GitHub forks](https://img.shields.io/github/forks/iocage/liblibiocage.svg)](https://github.com/iocage/libiocage/network)
[![GitHub stars](https://img.shields.io/github/stars/iocage/liblibiocage.svg)](https://github.com/iocage/libiocage/stargazers)
[![Twitter](https://img.shields.io/twitter/url/https/github.com/iocage/liblibiocage.svg?style=social)](https://twitter.com/intent/tweet?text=@iocage)

**Python Library to manage FreeBSD jails with libiocage.**

iocage is a jail/container manager amalgamating some of the best features and technologies the FreeBSD operating system has to offer. It is geared for ease of use with a simple and easy to understand command syntax.

This library provides programmatic access to iocage features and jails, while being compatible with iocage-legacy (bash), iocage-zfs and libiocage.

## Install

### from Source Distribution

```
pip3.6 install libiocage
```

### from Master branch

```
git clone https://github.com/iocage/libiocage
cd libiocage
make install
```

## Usage

### Library

```
import libiocage

jail = libiocage.Jail()
jail.create("11.1-RELEASE")
```

### CLI

Libiocage comes bundles with a CLI tool called `ioc`. It is inspired by the command line interface of https://github.com/iocage/iocage but meant to be developed among with the library and to spike on new features.
