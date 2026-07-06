# FreeBSD Test VM

The scripts in this directory run the libioc test suite inside a QEMU virtual machine with FreeBSD 13.5-RELEASE.
FreeBSD 13.5 is the newest release whose binary packages are still served for the 13.x branch, while staying close to the FreeBSD 12.1 environment that the original CI used.

The host in this repository has no KVM device, so QEMU runs in TCG software emulation.
Measured on a 12-core host: a boot takes one to two minutes, the guest setup with package installation ten to fifteen minutes, the first tier 2 run about six minutes including the release download, and the full suite about eight minutes once the release is fetched.

## Usage

The scripts are numbered in the order they are needed.

```sh
sh tools/vm/00-host-setup.sh    # install qemu, generate the SSH key
sh tools/vm/10-fetch-image.sh   # download, verify and unpack the VM image
sh tools/vm/20-provision.sh     # first boot: enable sshd via the VGA console
sh tools/vm/40-guest-setup.sh   # packages, fdescfs, ZFS pool, venv
sh tools/vm/50-run-tests.sh tier0   # import sweep
sh tools/vm/50-run-tests.sh tier1   # fast platform tests
sh tools/vm/50-run-tests.sh tier2   # jail lifecycle tests
sh tools/vm/50-run-tests.sh tier3   # full suite
sh tools/vm/50-run-tests.sh smoke   # end-to-end jail lifecycle
sh tools/vm/30-vm.sh down
```

`20-provision.sh` leaves the VM running, so `30-vm.sh up` is only needed for subsequent boots.
`30-vm.sh ssh [command]` opens a shell or runs a command inside the guest.
`30-vm.sh console` attaches to the serial console through the unix socket, which requires socat.

The official VM images route the console to the emulated VGA device, and the serial port stays silent during the first boot.
The provisioning script therefore types blindly into the VGA console through the QEMU monitor (`monitor_type.py`), and one of its first actions is persisting `console="comconsole"` in loader.conf, so every later boot is observable over the serial socket.
When something goes wrong, a screenshot of the VGA console shows the current state:

```sh
python3 tools/vm/monitor_type.py tools/vm/cache/mon.sock screendump /tmp/screen.png
```

## Design notes

The pristine image and all mutable state live in `tools/vm/cache/`, which is not committed.
The work image is a copy-on-write overlay on top of the pristine qcow2, so a broken guest is discarded by deleting `work.qcow2` and running `10-fetch-image.sh` again, followed by provisioning.
After a successful guest setup it is worth taking a snapshot while the VM is powered off: `qemu-img snapshot -c postsetup tools/vm/cache/work.qcow2`.

The archive server ftp-archive.freebsd.org only speaks plain HTTP, so `10-fetch-image.sh` verifies the download against a checksum pinned in `config.sh`.

FreeBSD 13 is past its end of life and pkg.freebsd.org can drop the `FreeBSD:13:amd64` repository at any time.
`40-guest-setup.sh` therefore mirrors the guest's package cache to `tools/vm/cache/pkg-cache/` after installation.
Should the repository disappear, the cached `.pkg` files can be copied back into the guest and installed with `pkg add`.

The test suite downloads the release tarballs from the archive mirror, because download.freebsd.org no longer carries 13.5.
The in-guest release mirror cache of the test suite keeps them under `/root/libioc/.cache/libioc` across runs.

## Expectations under QEMU

The VNET and bridge tests exercise the guest kernel and are expected to work.
Tests that require reachability of jail IP addresses from outside fail under QEMU's user-mode NAT and should be marked accordingly when encountered.
Fetching release updates through freebsd-update does not work for end-of-life releases, which is why the conftest disables it by default.
