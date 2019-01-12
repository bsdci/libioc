# Copyright (c) 2017-2019, Stefan Grönke
# Copyright (c) 2014-2018, iocage
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
"""Secure tarfile wrapper that prevents extraction of insecure paths."""
import typing
import tarfile

import libioc.errors


class SecureTarfile:
    """Secure tarfile wrapper that mitigates extraction of unsafe paths."""

    file: str
    file_open_mode: str = "r"
    compression_format: typing.Optional[str]
    logger: typing.Optional['libioc.Logger.Logger']

    def __init__(
        self,
        file: str,
        compression_format: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.file = file
        self.compression_format = compression_format
        self.logger = logger

    def _log(self, message: str, level: str="verbose") -> None:
        if self.logger is None:
            return
        self.logger.log(message, level)

    @property
    def mode(self) -> str:
        """Return the file mode for opening the archive file."""
        if self.compression_format is not None:
            return f"{self.file_open_mode}:{self.compression_format}"
        else:
            return self.file_open_mode

    def extract(self, destination: str) -> None:
        """
        Extract the tar file.

        Args:

            destination (str):

                Path to the archive file that is going to be extracted.
        """
        with tarfile.open(self.file, self.mode) as tar:
            self._log(f"Verifying file structure in {self.file}")
            self._check_tar_members(tar.getmembers())
            self._log(f"Extracting {self.file}")
            tar.extractall(destination)
            self._log(f"{self.file} was extracted to {destination}")

    def _check_tar_members(
        self,
        tar_infos: typing.List[typing.Any]
    ) -> None:
        for tar_member in tar_infos:
            self._check_tar_info(tar_member)

    def _check_tar_info(self, tar_info: typing.Any) -> None:
        if tar_info.name == ".":
            return
        if not tar_info.name.startswith("./"):
            reason = "Names in archives must be relative and begin with './'"
        elif ".." in tar_info.name:
            reason = "Names in archives must not contain '..'"
        else:
            return

        raise libioc.errors.IllegalArchiveContent(
            asset_name=self.file,
            reason=reason,
            logger=self.logger
        )


def extract(
    file: str,
    destination: str,
    compression_format: typing.Optional[str]=None,
    logger: typing.Optional['libioc.Logger.Logger']=None
) -> None:
    """
    Instantiate SecureTarfile and extract the archive files content.

    Args:

        file (str):

            Path to the source archive file.

        destination (str):

            Path to the extraction destination folder.

        logger (libioc.Logger.Logger):

            Logging is enabled when a Logger instance is provided.
    """
    secure_tarfile = SecureTarfile(file, logger=logger)
    secure_tarfile.extract(destination)
