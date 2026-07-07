# FreeBSD Test VM

The scripts in this directory run the libioc test suite inside a QEMU virtual machine with FreeBSD 13.5-RELEASE.
FreeBSD 13.5 is the newest release whose binary packages are still served for the 13.x branch, while staying close to the FreeBSD 12.1 environment that the original CI used.

The generic VM plumbing comes from the shared freebsd-ci tooling, which boots the official BASIC-CI images and provisions root SSH access.
`00-bootstrap.sh` installs the host packages and clones that tooling into `tools/vm/freebsd-ci/`, following the upstream main branch so that updates arrive without changes to this repository; `FREEBSD_CI_REF=<commit>` reproduces a historic state.
In CI the same tooling is consumed as composite actions on `@main`, see `.github/workflows/ci.yml`; both references move to `v1` once upstream tags it.
Only the libioc-specific guest setup and test runner live here.

## Usage

```sh
sh tools/vm/00-bootstrap.sh                # host deps + shared tooling
sh tools/vm/freebsd-ci/scripts/setup.sh    # image download, boot, provisioning
sh tools/vm/40-guest-setup.sh              # packages, fdescfs, ZFS pool, venv
sh tools/vm/50-run-tests.sh tier0          # import sweep
sh tools/vm/50-run-tests.sh tier1          # fast platform tests
sh tools/vm/50-run-tests.sh tier2          # jail lifecycle tests
sh tools/vm/50-run-tests.sh tier3          # full suite
sh tools/vm/50-run-tests.sh smoke          # end-to-end jail lifecycle
sh tools/vm/freebsd-ci/scripts/vm.sh down
```

The guest setup composes the shared guest helpers (`guest.sh` verbs for packages, kernel modules, tunables, fdescfs, the pool and the package cache mirror) and only defines the libioc package set, pool name and venv itself.

The shared scripts read their configuration from the environment; `tools/vm/config.sh` exports the libioc defaults (release 13.5-RELEASE, cache in `tools/vm/cache/`) before delegating, and the numbered scripts here source it.
When calling the shared scripts directly, export `FREEBSD_VERSION=13.5-RELEASE` and `FREEBSD_CI_CACHE=$(pwd)/tools/vm/cache` first, or accept their defaults with a separate cache under `~/.cache/freebsd-ci`.
`freebsd-ci/scripts/vm.sh` also offers `up`, `status`, `ssh [command]` and `console`.

## Design notes

The pristine image and all mutable state live in `tools/vm/cache/`, which is not committed.
The work image is a copy-on-write overlay on top of the pristine qcow2, so a broken guest is discarded by deleting `work.qcow2` and re-running the fetch and provision scripts.
After a successful guest setup it is worth taking a snapshot while the VM is powered off: `qemu-img snapshot -c postsetup tools/vm/cache/work.qcow2`.

FreeBSD 13 is past its end of life and pkg.freebsd.org can drop the `FreeBSD:13:amd64` repository at any time.
`40-guest-setup.sh` therefore mirrors the guest's package cache to `tools/vm/cache/pkg-cache/` after installation.
Should the repository disappear, the cached `.pkg` files can be copied back into the guest and installed with `pkg add`.

The test suite downloads the release tarballs from the archive mirror, because download.freebsd.org no longer carries 13.5.
The in-guest release mirror cache of the test suite keeps them under `/root/libioc/.cache/libioc` across runs.

## Performance

With KVM available a full suite run takes about two minutes of test time; under the TCG fallback on a KVM-less host it takes about nine.
The first tier 2 or tier 3 run additionally downloads the release into the guest.

## Expectations under QEMU

The VNET and bridge tests exercise the guest kernel and are expected to work.
Tests that require reachability of jail IP addresses from outside fail under QEMU's user-mode NAT and should be marked accordingly when encountered.
Fetching release updates through freebsd-update does not work for end-of-life releases, which is why the conftest disables it by default.
The resource limit tests need the kern.racct.enable tunable, which the guest setup persists, rebooting once when it was not active yet.
