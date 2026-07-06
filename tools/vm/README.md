# FreeBSD Test VM

The scripts in this directory run the libioc test suite inside a QEMU virtual machine with FreeBSD 13.5-RELEASE.
FreeBSD 13.5 is the newest release whose binary packages are still served for the 13.x branch, while staying close to the FreeBSD 12.1 environment that the original CI used.
The VM boots the official BASIC-CI image, which ships with a serial console, DHCP, growfs and an sshd that accepts root with an empty password on the first boot, so the whole setup runs over SSH.

The host in this repository has no KVM device, so QEMU runs in TCG software emulation.
Measured on a 12-core host: a boot takes one to two minutes, the guest setup with package installation ten to fifteen minutes, the first tier 2 run about six minutes including the release download, and the full suite about eight minutes once the release is fetched.

## Usage

The scripts are numbered in the order they are needed.

```sh
sh tools/vm/00-host-setup.sh    # install qemu, generate the SSH key
sh tools/vm/10-fetch-image.sh   # download, verify and unpack the CI image
sh tools/vm/20-provision.sh     # first boot: install the SSH key over SSH
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

Provisioning waits for sshd, logs in as root with the empty password the BASIC-CI image ships with, installs the SSH key and closes the empty-password access again.
The forwarded SSH port only binds to 127.0.0.1, so the empty-password window is not reachable from outside the host.
The BASIC-CI image routes its console to both the serial port and the VGA device, so `30-vm.sh console` shows the boot from the very first second.
When even the serial console stays quiet, the QEMU monitor socket saves a screenshot of the VGA display:

```sh
printf 'screendump /tmp/screen.png -f png\n' | socat - UNIX-CONNECT:tools/vm/cache/mon.sock
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
