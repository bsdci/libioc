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
"""Collection of iocage errors."""
import typing

# MyPy
import libzfs  # noqa: F401
import libioc.Types  # noqa: F401
import libioc.Logger


class IocException(Exception):
    """A well-known exception raised by liblibioc."""

    def __init__(
        self,
        message: str,
        level: str="error",
        silent: bool=False,
        append_warning: bool=False,
        warning: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        if (logger is not None) and (silent is False):
            logger.__getattribute__(level)(message)
            if (append_warning is True) and (warning is not None):
                logger.warn(warning)
        else:
            super().__init__(message)


# Missing Features


class MissingFeature(IocException, NotImplementedError):
    """Raised when an iocage feature is not fully implemented yet."""

    def __init__(
        self,
        feature_name: str,
        plural: bool=False,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        message = (
            f"Missing Feature: '{feature_name}' "
            f"{'are' if plural is True else 'is'} not implemented yet"
        )
        IocException.__init__(self, message=message)


# Jails


class JailException(IocException):
    """Raised when an exception related to a jail occurs."""

    jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.jail = jail
        IocException.__init__(self, message=message, logger=logger)


class JailDoesNotExist(JailException):
    """Raised when the jail does not exist."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' does not exist"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailAlreadyExists(IocException):
    """Raised when the jail already exists."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' already exists"
        IocException.__init__(self, message=msg, logger=logger)


class JailNotRunning(IocException):
    """Raised when the jail is not running."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' is not running"
        IocException.__init__(self, message=msg, logger=logger)


class JailAlreadyRunning(IocException):
    """Raised when the jail is already running."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Jail '{jail.humanreadable_name}' is already running"
        IocException.__init__(self, message=msg, logger=logger)


class JailNotFound(IocException):
    """Raised when the jail was not found."""

    def __init__(
        self,
        text: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"No jail matching '{text}' was found"
        IocException.__init__(self, message=msg, logger=logger)


class JailNotSupplied(IocException):
    """Raised when no jail was supplied."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Please supply a jail"
        IocException.__init__(self, message=msg, logger=logger)


class JailUnknownIdentifier(IocException):
    """Raised when the jail has an unknown identifier."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "The jail has no identifier yet"
        IocException.__init__(self, message=msg, logger=logger)


class JailBackendMissing(IocException):
    """Raised when the jails backend was not found."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "The jail backend is unknown"
        IocException.__init__(self, message=msg, logger=logger)


class JailIsTemplate(JailException):
    """Raised when the jail is a template but should not be."""

    jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The jail '{jail.name}' is a template"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailNotTemplate(JailException):
    """Raised when the jail is no template but should be one."""

    jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The jail '{jail.full_name}' is not a template"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailHookFailed(JailException):
    """Raised when the jail could not be launched."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        hook: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.hook = hook
        msg = f"Jail {jail.full_name} hook {hook} failed"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailLaunchFailed(JailException):
    """Raised when the jail could not be launched."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Launching jail {jail.full_name} failed"
        if reason is not None:
            msg += f": {reason}"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailDestructionFailed(JailException):
    """Raised when the jail could not be destroyed."""

    jail: 'libioc.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Destroying jail {jail.full_name} failed"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailCommandFailed(IocException):
    """Raised when a jail command fails with an exit code > 0."""

    returncode: int

    def __init__(
        self,
        returncode: int,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.returncode = returncode
        msg = f"Jail command exited with {returncode}"
        IocException.__init__(self, message=msg, logger=logger)


class JailExecutionAborted(JailException):
    """Raised when a jail command fails with an exit code > 0."""

    def __init__(
        self,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Jail execution of {jail.humanreadable_name} aborted"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


# Jail State


class JailStateUpdateFailed(IocException):
    """Raised when a JLS query failed."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"JLS query failed"
        IocException.__init__(self, message=msg, logger=logger)


# Jail Fstab


class VirtualFstabLineHasNoRealIndex(IocException):
    """Raised when attempting to access the index of a virtual fstab line."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The virtual fstab line does not have a real list index"
        IocException.__init__(self, message=msg, logger=logger)


class FstabDestinationExists(IocException):
    """Raised when the destination directory does not exist."""

    def __init__(
        self,
        mountpoint: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The mountpoint {mountpoint} already exists in the fstab file"
        IocException.__init__(self, message=msg, logger=logger)


# Security


class SecurityViolation(IocException):
    """Raised when iocage has security concerns."""

    def __init__(
        self,
        reason: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Security violation: {reason}"
        IocException.__init__(self, message=msg, logger=logger)


class InsecureJailPath(SecurityViolation):
    """Raised when a a path points outside of a resource."""

    def __init__(
        self,
        path: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Insecure path {path} jail escape attempt"
        SecurityViolation.__init__(self, reason=msg)


class SecurityViolationConfigJailEscape(SecurityViolation):
    """Raised when a file symlinks to a location outside of the jail."""

    def __init__(
        self,
        file: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The file {file} references a file outsite of the jail resource"
        SecurityViolation.__init__(self, reason=msg)


class IllegalArchiveContent(IocException):
    """Raised when a release asset archive contains malicious content."""

    def __init__(
        self,
        asset_name: str,
        reason: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Asset {asset_name} contains illegal files - {reason}"
        super().__init__(message=msg, logger=logger)


# JailConfig


class JailConfigError(IocException):
    """Raised when a general configuration error occurs."""

    pass


class InvalidJailName(JailConfigError):
    """Raised when a jail has an invalid name."""

    def __init__(
        self,
        name: str,
        invalid_characters: typing.Optional[typing.List[str]]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            f"Invalid jail name '{name}': "
            "Names may only contain alphanumeric characters and dash"
        )
        if invalid_characters is not None:
            msg += ", but got " + str("".join(invalid_characters) + "")
        super().__init__(message=msg, logger=logger)


class JailConigZFSIsNotAllowed(JailConfigError):
    """Raised when a jail is not allowed to use ZFS shares."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            "jail_zfs is disabled "
            "despite jail_zfs_dataset is configured"
        )
        super().__init__(message=msg, logger=logger)


class InvalidJailConfigValue(JailConfigError, ValueError):
    """Raised when a jail configuration value is invalid."""

    def __init__(
        self,
        property_name: str,
        jail: typing.Optional['libioc.Jail.JailGenerator']=None,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error"
    ) -> None:

        msg = f"Invalid value for property '{property_name}'"
        if jail is not None:
            msg += f" of jail {jail.humanreadable_name}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger, level=level)


class InvalidJailConfigAddress(InvalidJailConfigValue):
    """Raised when a jail address is invalid."""

    def __init__(
        self,
        value: str,
        property_name: str,
        jail: typing.Optional['libioc.Jail.JailGenerator']=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error"
    ) -> None:
        reason = f"expected \"<nic>|<address>\" but got \"{value}\""
        super().__init__(
            property_name=property_name,
            jail=jail,
            reason=reason,
            level=level,
            logger=logger
        )


class InvalidMacAddress(IocException, ValueError):
    """Raised when a jail MAC address is invalid."""

    def __init__(
        self,
        mac_address: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        reason = f"invalid mac address: \"{mac_address}\""
        IocException.__init__(
            self,
            message=reason
        )


class ResourceLimitUnknown(IocException, KeyError):
    """Raised when a resource limit has is unknown."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The specified resource limit is unknown"
        IocException.__init__(self, message=msg, logger=logger)


class ResourceLimitActionFailed(IocException, KeyError):
    """Raised when a resource limit has is unknown."""

    def __init__(
        self,
        action: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Resource Limit failed to {action}"
        IocException.__init__(self, message=msg, logger=logger)


class JailHostIdMismatch(JailException):
    """Raised when attempting to start a jail with mismatching hostid."""

    def __init__(
        self,
        host_hostid: str,
        jail: 'libioc.Jail.JailGenerator',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        jail_hostid = jail.config["hostid"]
        msg = (
            f"The jail hostid '{jail_hostid}' "
            f"does not match the hosts hostid '{host_hostid}'"
        )
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailConfigNotFound(IocException):
    """Raised when a jail is not configured."""

    def __init__(
        self,
        config_type: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Could not read {config_type} config"
        # This is a silent error internally used
        IocException.__init__(self, message=msg, logger=logger)


class DefaultConfigNotFound(IocException, FileNotFoundError):
    """Raised when no default config was found on the host."""

    def __init__(
        self,
        config_file_path: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Default configuration not found at {config_file_path}"
        IocException.__init__(self, message=msg, logger=logger)


class UnknownConfigProperty(IocException, KeyError):
    """Raised when a unknown jail config property was used."""

    def __init__(
        self,
        key: str,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error",
        jail: typing.Optional['libioc.Jail.JailGenerator']=None
    ) -> None:
        if jail is None:
            msg = f"The config property '{key}' is unknown"
        else:
            msg = (
                f"The config property '{key}' of jail '{jail.name}' is unknown"
            )
        self.jail = jail
        IocException.__init__(
            self,
            message=msg,
            logger=logger,
            level=level
        )


# Backup


class BackupInProgress(IocException):
    """Raised when a backup operation is already in progress."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "A backup operation is already in progress"
        IocException.__init__(self, message=msg, logger=logger)


class ExportDestinationExists(IocException):
    """Raised when a backup operation is already in progress."""

    def __init__(
        self,
        destination: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "The backup destination {destination} already exists"
        IocException.__init__(self, message=msg, logger=logger)


class BackupSourceDoesNotExist(IocException):
    """Raised when a backup source is not available for import."""

    def __init__(
        self,
        source: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "The backup source {source} does not exists"
        IocException.__init__(self, message=msg, logger=logger)


class BackupSourceUnknownFormat(IocException):
    """Raised when a backup source is in unknown format."""

    def __init__(
        self,
        source: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "The backup source {source} has unknown type"
        IocException.__init__(self, message=msg, logger=logger)


# ListableResource


class ListableResourceNamespaceUndefined(IocException):
    """Raised when a ListableResource was not defined with a namespace."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The ListableResource needs a namespace for this operation"
        IocException.__init__(self, message=msg, logger=logger)


# General


class IocageNotActivated(IocException):
    """Raised when iocage is not active on any ZFS pool."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            "iocage is not activated yet - "
            "please run `ioc activate <POOL>` first and select a pool"
        )
        super().__init__(message=msg, logger=logger)


class ActivationFailed(IocException):
    """Raised when ZFS pool activation failed."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "iocage ZFS pool activation failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class ZFSSourceMountpoint(IocException):
    """Raised when iocage could not determine its mountpoint."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            f"Mountpoint of iocage ZFS source dataset '{dataset_name}'"
            " is unset and cannot be determined automatically"
        )
        super().__init__(message=msg, logger=logger)


class InvalidLogLevel(IocException):
    """Raised when the logger was initialized with an invalid log level."""

    def __init__(
        self,
        log_level: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        available_log_levels = libioc.Logger.Logger.LOG_LEVELS
        available_log_levels_string = ", ".join(available_log_levels[:-1])
        msg = (
            f"Invalid log-level {log_level}. Choose one of "
            f"{available_log_levels_string} or {available_log_levels[-1]}"
        )
        super().__init__(message=msg, logger=logger)


class MustBeRoot(IocException):
    """Raised when iocage is executed without root permission."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        _msg = (
            f"Must be root to {message}"
        )
        super().__init__(message=_msg, logger=logger)


class CommandFailure(IocException):
    """Raised when iocage fails to execute a command."""

    def __init__(
        self,
        returncode: int,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Command exited with {returncode}"
        super().__init__(message=msg, logger=logger)


class NotAnIocageZFSProperty(IocException):
    """Raised when iocage attempts to touch a non-iocage ZFS property."""

    def __init__(
        self,
        property_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The ZFS property '{property_name}' is not managed by iocage"
        super().__init__(message=msg, logger=logger)


# Host, Distribution


class DistributionUnknown(IocException):
    """Raised when the host distribution is unknown or not supported."""

    def __init__(
        self,
        distribution_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Unknown Distribution: {distribution_name}"
        super().__init__(message=msg, logger=logger)


class HostReleaseUnknown(IocException):
    """Raised when the host release could not be determined."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"The host release is unknown"
        super().__init__(message=msg, logger=logger)


class HostUserlandVersionUnknown(IocException):
    """Raised when the hosts userland version could not be detected."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Could not determine the hosts userland version"
        super().__init__(message=msg, logger=logger)


class DownloadFailed(IocException):
    """Raised when downloading EOL warnings failed."""

    def __init__(
        self,
        url: str,
        code: int,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error"
    ) -> None:
        msg = f"Failed downloading {url}: {code}"
        super().__init__(message=msg, logger=logger, level=level)


# Storage


class DatasetExists(IocException):
    """Raised when a dataset already exists."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Dataset already exists: {dataset_name}"
        super().__init__(message=msg, logger=logger)


class UnmountFailed(IocException):
    """Raised when an unmount operation fails."""

    def __init__(
        self,
        mountpoint: typing.Any=None,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        if mountpoint is None:
            msg = "Umount failed"
        else:
            msg = f"Unmount of {mountpoint} failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class MountFailed(IocException):
    """Raised when a mount operation fails."""

    def __init__(
        self,
        mountpoint: libioc.Types.AbsolutePath,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Failed to mount {mountpoint}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class InvalidMountpoint(IocException):
    """Raised when a mountpoint was invalid or not found."""

    def __init__(
        self,
        mountpoint: libioc.Types.AbsolutePath,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Invalid mountpoint {mountpoint}"
        super().__init__(message=msg, logger=logger)


class DatasetNotMounted(IocException):
    """Raised when a dataset is not mounted but should be."""

    def __init__(
        self,
        dataset: 'libzfs.ZFSDataset',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Dataset '{dataset.name}' is not mounted"
        super().__init__(message=msg, logger=logger)


class DatasetNotAvailable(IocException):
    """Raised when a dataset is not available."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Dataset '{dataset_name}' is not available"
        super().__init__(message=msg, logger=logger)


class DatasetNotJailed(IocException):
    """Raised when a ZFS share was not flagged as such."""

    def __init__(
        self,
        dataset: 'libzfs.ZFSDataset',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        name = dataset.name
        msg = f"Dataset {name} is not jailed."
        warning = f"Run 'zfs set jailed=on {name}' to allow mounting"
        super().__init__(
            msg,
            warning=warning,
            append_warning=True
        )


class ZFSException(IocException):
    """Raised when a ZFS pool not available."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        super().__init__(message=message, logger=logger)


class ZFSPoolInvalid(IocException, TypeError):
    """Raised when a ZFS pool is invalid."""

    def __init__(
        self,
        consequence: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "Invalid ZFS pool"

        if consequence is not None:
            msg += f": {consequence}"

        IocException.__init__(self, message=msg, logger=logger)


class ZFSPoolUnavailable(IocException):
    """Raised when a ZFS pool not available."""

    def __init__(
        self,
        pool_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"ZFS pool '{pool_name}' is UNAVAIL"
        super().__init__(message=msg, logger=logger)


class ResourceUnmanaged(IocException):
    """Raised when locating a resources dataset on a root dataset fails."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"The resource dataset {dataset_name} is not managed by iocage"
        super().__init__(message=msg, logger=logger)


class ConflictingResourceSelection(IocException):
    """Raised when a resource was configured with conflicting sources."""

    def __init__(
        self,
        source_a: str,
        source_b: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = (
            "The resource was configured with conflicting root sources: "
            f"{source_a} != {source_b}"
        )
        super().__init__(message=msg, logger=logger)


# Snapshots


class SnapshotError(IocException):
    """Raised on snapshot related errors."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class SnapshotCreation(SnapshotError):
    """Raised when creating a snapshot failed."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "Snapshot creation failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class SnapshotDeletion(SnapshotError):
    """Raised when deleting a snapshot failed."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "Snapshot deletion failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class SnapshotRollback(SnapshotError):
    """Raised when rolling back a snapshot failed."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "Snapshot rollback failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class SnapshotNotFound(SnapshotError):
    """Raised when a snapshot was not found."""

    def __init__(
        self,
        snapshot_name: str,
        dataset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Snapshot not found: {dataset_name}@{snapshot_name}"
        super().__init__(message=msg, logger=logger)


class InvalidSnapshotIdentifier(SnapshotError):
    """Raised when a snapshot identifier is invalid."""

    def __init__(
        self,
        identifier: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = (
            f"Invalid snapshot identifier syntax: {identifier}"
            "(should be <jail>@<snapshot>)"
        )
        super().__init__(message=msg, logger=logger)


# Network


class InvalidInterfaceName(IocException):
    """Raised when a NIC name is invalid."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "Invalid NIC name"
        super().__init__(message=msg, logger=logger)


class VnetBridgeMissing(IocException):
    """Raised when a vnet bridge is missing."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "VNET is enabled and requires setting a bridge"
        super().__init__(message=msg, logger=logger)


class VnetBridgeDoesNotExist(IocException):
    """Raised when a vnet bridge is missing."""

    def __init__(
        self,
        bridge_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"VNET bridge {bridge_name} does not exist"
        super().__init__(message=msg, logger=logger)


class InvalidNetworkBridge(IocException, ValueError):
    """Raised when a network bridge is invalid."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = "Invalid network bridge argument"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class FirewallDisabled(IocException):
    """Raised when the firewall is required but disabled (Secure VNET)."""

    def __init__(
        self,
        hint: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "IPFW is disabled"
        if hint is not None:
            msg += f": {hint}"
        super().__init__(message=msg, logger=logger)


class FirewallCommandFailure(IocException):
    """Raised when a firewall command fails (Secure VNET)."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "Firewall Command failed. Is IPFW enabled?"
        super().__init__(message=msg, logger=logger)


class InvalidIPAddress(IocException):
    """Raised when an invalid IP address was assigned to a network."""

    def __init__(
        self,
        reason: str,
        ipv6: bool,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error"
    ) -> None:
        ip_version = 4 + 2 * (ipv6 is True)
        msg = f"Invalid IPv{ip_version} address: {reason}"
        super().__init__(message=msg, logger=logger, level=level)


# Release


class ReleaseListUnavailable(IocException):
    """Raised when the list could not be downloaded from the remote."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"The releases list is unavailable"
        super().__init__(message=msg, logger=logger)


class ReleaseAssetHashesUnavailable(IocException):
    """Raised when the list could not be downloaded from the remote."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"The releases asset hashes are unavailable"
        super().__init__(message=msg, logger=logger)


class UpdateFailure(IocException):
    """Raised when an update fails."""

    def __init__(
        self,
        name: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None,
        level: str="error"
    ) -> None:

        msg = f"Release update of '{name}' failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger, level=level)


class InvalidReleaseAssetSignature(UpdateFailure):
    """Raised when a release signature is invalid."""

    def __init__(
        self,
        name: str,
        asset_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Asset {asset_name} has an invalid signature"
        UpdateFailure.__init__(
            self,
            name=name,
            reason=msg
        )


class NonReleaseUpdateFetch(UpdateFailure):
    """Raised when attempting to fetch updates for a custom release."""

    def __init__(
        self,
        resource: 'libioc.Resource.Resource',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:

        msg = f"Updates can only be fetched for releases"
        UpdateFailure.__init__(
            self,
            name=resource.name,
            reason=msg
        )


class ReleaseNotFetched(IocException):
    """Raised when a release was not yet fetched."""

    def __init__(
        self,
        name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Release '{name}' does not exist or is not fetched locally"
        super().__init__(message=msg, logger=logger)


class ReleaseUpdateBranchLookup(IocException):
    """Raised when failing to lookup the remote update branch."""

    def __init__(
        self,
        release_name: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Update source of release '{release_name}' not found"
        if reason is not None:
            msg += ": {reason}"
        super().__init__(message=msg, logger=logger)


class UnsupportedRelease(MissingFeature):
    """Raised when interacting with an unsupported release."""

    def __init__(
        self,
        version: float,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        feature_name = f"Support for release version {version}"
        super().__init__(
            feature_name=feature_name,
            plural=True
        )


class InvalidReleaseName(IocException):
    """Raised when interacting with an unsupported release."""

    def __init__(
        self,
        name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Invalid release name: {name}"
        super().__init__(message=msg, logger=logger)


# Prompts


class DefaultReleaseNotFound(IocException):
    """Raised when the default (host) release does not match a remote."""

    def __init__(
        self,
        host_release_name: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            f"Release '{host_release_name}' not found: "
            "Could not determine a default source"
        )
        super().__init__(message=msg, logger=logger)


# DevfsRules


class DevfsRuleException(IocException):
    """Raised on errors in devfs rules."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class InvalidDevfsRulesSyntax(DevfsRuleException):
    """Raised when a devfs rule has invalid syntax."""

    def __init__(
        self,
        devfs_rules_file: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Invalid devfs rules in {devfs_rules_file}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class DuplicateDevfsRuleset(DevfsRuleException):
    """Raised when a duplicate devfs rule was found."""

    def __init__(
        self,
        devfs_rules_file: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "Cannot add duplicate ruleset"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class MissingDevfsRulesetName(DevfsRuleException):
    """Raised when a duplicate devfs rule was found."""

    def __init__(
        self,
        devfs_rules_file: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "The devfs ruleset is missing a name"
        super().__init__(message=msg, logger=logger)

# Logger


class LogException(IocException):
    """Raised when logging fails."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class CannotRedrawLine(LogException):
    """Raised when manipulating previous log entries fails."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "Logger can't redraw line"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


# Events


class EventAlreadyFinished(IocException):
    """Raised when a event is touched that was already finished."""

    def __init__(
        self,
        event: 'libioc.events.IocEvent',
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = "This {event.type} event is already finished"
        IocException.__init__(self, message=msg, logger=logger)


# Jail Filter


class JailFilterException(IocException):
    """Raised when a jail filter is invalid."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        IocException.__init__(self, message=message, logger=logger)


class JailFilterInvalidName(JailFilterException):
    """Raised when the name of a jail filter is invalid."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        message = (
            "Invalid jail selector: "
            "Cannot select jail with illegal name"
        )
        JailFilterException.__init__(self, message=message, logger=logger)


# pkg


class PkgNotFound(IocException):
    """Raised when the pkg package was not found in the local mirror."""

    def __init__(
        self,
        message: typing.Optional[str]=None,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        if message is None:
            message = "The pkg package was not found in the local mirror."
        IocException.__init__(self, message=message, logger=logger)


# Provisioning


class UndefinedProvisionerSource(IocException):
    """Raised when a provisioner source is not set."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Missing provisioner source"
        IocException.__init__(self, message=msg, logger=logger)


class UndefinedProvisionerMethod(IocException):
    """Raised when a provisioner method is not set."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Missing provisioner method"
        IocException.__init__(self, message=msg, logger=logger)


# Sources


class InvalidSourceName(IocException):
    """Raised when a source name is invalid."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = (
            "Invalid source name: "
            "A source name may contain letters A-z, dash and lowdash"
        )
        super().__init__(message=msg, logger=logger)


class SourceNotFound(IocException):
    """Raised when a source was not found."""

    def __init__(
        self,
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        msg = f"Jail source not found"
        super().__init__(message=msg, logger=logger)
