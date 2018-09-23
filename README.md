# libiocage

**Python Library to manage FreeBSD jails with libiocage.**

iocage is a jail/container manager fusioning some of the best features and technologies the FreeBSD operating system has to offer.
It is geared for ease of use with a simple and easy to understand command syntax.

This library provides programmatic access to iocage features and jails, while aiming to be compatible with iocage-legacy, and the current Python 3 version of iocage.

### Latest News (September 22nd, 2018)
Progress towards the transition of [python-iocage](https://github.com/iocage/iocage) using libiocage has been made.
Recent changes to both projects ensure compatibility running on the same host, so that it is now possible to partially utilize libiocage in iocage until a full migration is performed.
Because some changes to the command line arguments and the script output will occur, @skarekrow will continue to maintain the current implementation until users had time to follow the deprecation warnings and suggestions.

In terms of the "Advanced container management with libiocage" tutorial at EuroBSDCon 2018 the [Handbook](https://iocage.github.com/handbook) was published.

## Install

```sh
git clone https://github.com/iocage/libiocage
cd libiocage
make install
```

At the current time libiocage is not packaged or available in FreeBSD ports.

## Documentation

- Iocage Handbook: https://iocage.github.com/handbook
- Reference Documentation: https://iocage.github.io/libiocage

## Configuration

### Active ZFS pool

libiocage iterates over existing ZFS pools and stops at the first one with ZFS property `org.freebsd.ioc:active` set to `yes`.
This behavior is the default used by other iocage variants and is restricted to one pool managed by iocage

### Root Datasets configured in /etc/rc.conf

When iocage datasets are specified in the jail hosts `/etc/rc.conf`, libiocage prefers them over activated pool lookups.
Every ZFS filesystem that iocage should use as root dataset has a distinct name and is configured as `ioc_dataset_<NAME>="zroot/some-dataset/iocage"`, for example:

```
$ cat /etc/rc.conf | grep ^ioc_dataset
ioc_dataset_mysource="zroot/mysource/iocage"
ioc_dataset_othersource="zroot/iocage"
```

iocage commands default to the first root data source specified in the file.
Operations can be pointed to an alternative root by prefixing the subject with the source name followed by a slash.

```sh
ioc create othersource/myjail
ioc rename othersource/myjail myjail2
```

When `othersource` is the only datasource with a jail named `myjail` the above operation would have worked without explicitly stating the dataset name.

## Usage

### Library

```python
import iocage

jail = iocage.Jail()
jail.create("11.1-RELEASE")
```

### CLI

Libiocage comes bundles with a CLI tool called `ioc`.
It is inspired by the command line interface of [iocage](https://github.com/iocage/iocage) but meant to be developed along with the library and to spike on new features.

```
Usage: ioc [OPTIONS] COMMAND [ARGS]...

  A jail manager.

Options:
  --version             Show the version and exit.
  --source TEXT         Globally override the activated iocage dataset(s)
  -d, --log-level TEXT  Set the CLI log level ('critical', 'error', 'warn',
                        'info', 'notice', 'verbose', 'debug', 'spam',
                        'screen')
  --help                Show this message and exit.

Commands:
  activate    Set a zpool active for iocage usage.
  clone       Clone and promote jails.
  console     Login to a jail.
  create      Create a jail.
  deactivate  Disable a ZFS pool for iocage.
  destroy     Destroy specified resource
  exec        Run a command inside a specified jail.
  export      Export a jail to a backup archive
  fetch       Fetch and update a Release to create Jails...
  fstab       View and manipulate a jails fstab file.
  get         Gets the specified property.
  import      Import a jail from a backup archive
  list        List a specified dataset type, by default...
  migrate     Migrate jails to the latest format.
  pkg         Manage packages in a jail.
  promote     Clone and promote jails.
  provision   Trigger provisioning of jails.
  rename      Rename a stopped jail.
  restart     Restarts the specified jails.
  set         Sets the specified property.
  snapshot    Take and manage resource snapshots.
  start       Starts the specified jails or ALL.
  stop        Stops the specified jails or ALL.
  update      Starts the specified jails or ALL.
```

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

## Documentation

The [API Reference (html)](https://iocage.github.io/libiocage) documenting all public interfaces of libiocage is updated with every release.
The information found in the reference is compiled from Python docstrings and MyPy typings using Sphinx.

## Development

### Unit Tests

Unit tests may run on FreeBSD or HardenedBSD and require an activated iocage pool.

```sh
ZPOOL=zroot make test
```

### Static Code Analysis

The project enforces PEP-8 code style and MyPy strong typing via flake8, that is required to pass before merging any changes.
Together with Bandit checks for common security issues the static code analysis can be ran on Linux and BSD as both do not require py-libzfs or code execution.

```
make install-dev
make check
```

---

### Project Status (Archive)

#### 2018-08-07
libiocage is making small but continuous steps to stabilize the interfaces and become used in [iocage/iocage](https://github.com/iocage/iocage).
The project was first presented in the talk "[Imprisoning software with libiocage](https://www.bsdcan.org/2018/schedule/events/957.en.html)" at BSDCan 2018 (Video Recording on [YouTube](https://www.youtube.com/watch?v=CTGc3zYToh0)).
There will be a Tutorial about [Advanced container management with libiocage](https://2018.eurobsdcon.org/tutorial-speakers/#StefanGronke) on September 20th, 2018 at EuroBSDCon in Bucharest.

Ongoing preparations at this repository and iocage ensure that the transition to using libiocage under the hood of iocage go as smooth as possible for users.
Features that exist in iocage will be further improved and tested or announced to be replaced or deprecated shortly.
iXsystems let one imagine that libiocage once finds its way into FreeNAS where it can play its full strength behind a Web GUI.

#### 2017-11-14
As of November 2017 this project is *working towards an alpha release*.
This means stabilization of command-line and library interfaces, so that proper integration tests can be built.
This phase requires manual verification and testing until reaching feature-completion and compatibility with Python [iocage](https://github.com/iocage/iocage) and prior iocage_legacy versions with [ZFS property](https://github.com/iocage/iocage_legacy/tree/master) and [UCL file](https://github.com/iocage/iocage_legacy) config storage.
