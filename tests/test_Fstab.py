# Copyright (c) 2017-2019, Stefan Grönke
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Unit tests for Fstab module."""
import pytest
import tempfile
import random
import sys
import os.path
import subprocess

import libzfs

import libioc.Config.Jail.File.Fstab

class TestFstab(object):
	"""Run Fstab unit tests."""

	def test_can_read_files_with_utf8(
		self
	) -> None:

		temp_file = tempfile.NamedTemporaryFile()
		content = "# Stefan Grönke was here."
		temp_file.write(content.encode("utf-8"))
		temp_file.seek(0)

		fstab = libioc.Config.Jail.File.Fstab.Fstab(file=temp_file.name)

		assert len(fstab) == 1

	def test_can_read_files_with_comment_and_fstab_line(
		self
	) -> None:

		temp_file = tempfile.NamedTemporaryFile()
		content = """# This is a comment\twith tabs
fdescfs /dev/fd fdescfs rw	0 0"""
		assert content.count("\n") == 1
		
		temp_file.write(content.encode("utf-8"))
		temp_file.seek(0)

		fstab = libioc.Config.Jail.File.Fstab.Fstab(file=temp_file.name)

		assert len(fstab) == 2
		assert type(fstab[0]).__name__ == "FstabCommentLine"
		assert str(fstab[0]) == "# This is a comment\twith tabs"
		assert type(fstab[1]).__name__ == "FstabLine"
		assert str(fstab[1]) == "fdescfs\t/dev/fd\tfdescfs\trw\t0\t0"

	def test_parses_auto_lines(
		self
	) -> None:

		AUTO_COMMENT_IDENTIFIER = "iocage-auto"
		temp_file = tempfile.NamedTemporaryFile()
		content = f"""# This is a comment\twith tabs
fdescfs /dev/fd fdescfs rw	0 0 # {AUTO_COMMENT_IDENTIFIER}
tmpfs /tmp tmpfs rw,mode=777 0 0 # {AUTO_COMMENT_IDENTIFIER}
# yet another comment line
tmpfs /tmp tmpfs rw,mode=777 0 0 # {AUTO_COMMENT_IDENTIFIER}"""
		assert content.count("\n") == 4
		
		temp_file.write(content.encode("utf-8"))
		temp_file.seek(0)

		fstab = libioc.Config.Jail.File.Fstab.Fstab(file=temp_file.name)

		# only 3 lines are expected
		assert len(fstab) == 3

		assert type(fstab[0]).__name__ == "FstabCommentLine"
		assert str(fstab[0]) == "# This is a comment\twith tabs"
		assert type(fstab[1]).__name__ == "FstabAutoPlaceholderLine"
		assert type(fstab[2]).__name__ == "FstabCommentLine"
		assert str(fstab[2]) == "# yet another comment line"

	@pytest.fixture(scope="function")
	def zfs_volume(
		self,
		root_dataset: libzfs.ZFSDataset,
		zfs: libzfs.ZFS
	) -> libzfs.ZFSDataset:

		r = random.randint(0, sys.maxsize)
		dataset_name = f"{root_dataset.name}/zvol{r}"

		root_dataset.pool.create(
			dataset_name,
			fsopts=dict(volsize="16M"),
			fstype=libzfs.DatasetType.VOLUME
		)

		dataset = zfs.get_dataset(dataset_name)
		yield dataset

		dataset.delete()

	@pytest.fixture(scope="function")
	def zfs_volume_ufs(
		self,
		zfs_volume: libzfs.ZFSDataset
	) -> libzfs.ZFSDataset:

		subprocess.Popen(
			[
				"/sbin/newfs",
				f"/dev/zvol/{zfs_volume.name}"
			]
		).wait()

		return zfs_volume

	def test_ufs_mount(self, zfs_volume_ufs: libzfs.ZFSDataset) -> None:

		with tempfile.TemporaryDirectory() as tmpdir:

			assert os.path.isdir(tmpdir)
			libioc.helpers.mount(
				source=f"/dev/zvol/{zfs_volume_ufs.name}",
				destination=tmpdir,
				fstype="ufs"
			)

			try:
				stdout = subprocess.check_output(
					[f"/sbin/mount | grep {tmpdir} | wc -l"],
					shell=True
				).decode("utf-8").strip()
				assert stdout == "1"

				assert os.path.isdir(tmpdir)

				testfile = os.path.join(tmpdir, "test.txt")
				with open(testfile, "w+") as f:
					f.write("Test the ability to mount ZFS volumes with UFS")

				assert os.path.exists(testfile) is True
			finally:
				subprocess.Popen([
					f"/sbin/umount", tmpdir
				]).wait()

			assert os.path.exists(testfile) is False
