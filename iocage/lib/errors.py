# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
import iocage.lib.events  # noqa: F401
import iocage.lib.Jail  # noqa: F401
import iocage.lib.Types  # noqa: F401
from iocage.lib.Logger import Logger


class IocageException(Exception):
    """A well-known exception raised by libiocage."""

    def __init__(
        self,
        message: str,
        level: str="error",
        silent: bool=False,
        append_warning: bool=False,
        warning: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:
        if (logger is not None) and (silent is False):
            logger.__getattribute__(level)(message)
            if (append_warning is True) and (warning is not None):
                logger.warn(warning)
        else:
            super().__init__(message)


# Missing Features


class MissingFeature(IocageException, NotImplementedError):
    """Raised when an iocage feature is not fully implemented yet."""

    def __init__(
        self,
        feature_name: str,
        plural: bool=False,
        logger: typing.Optional[Logger]=None
    ) -> None:
        message = (
            f"Missing Feature: '{feature_name}' "
            f"{'are' if plural is True else 'is'} not implemented yet"
        )
        IocageException.__init__(self, message=message)


# Jails


class JailException(IocageException):
    """Raised when an exception related to a jail occurs."""

    jail: 'iocage.lib.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        self.jail = jail
        IocageException.__init__(self, message=message, logger=logger)


class JailDoesNotExist(JailException):
    """Raised when the jail does not exist."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' does not exist"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailAlreadyExists(IocageException):
    """Raised when the jail already exists."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' already exists"
        IocageException.__init__(self, message=msg, logger=logger)


class JailNotRunning(IocageException):
    """Raised when the jail is not running."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Jail '{jail.humanreadable_name}' is not running"
        IocageException.__init__(self, message=msg, logger=logger)


class JailAlreadyRunning(IocageException):
    """Raised when the jail is already running."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Jail '{jail.humanreadable_name}' is already running"
        IocageException.__init__(self, message=msg, logger=logger)


class JailNotFound(IocageException):
    """Raised when the jail was not found."""

    def __init__(
        self,
        text: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"No jail matching '{text}' was found"
        IocageException.__init__(self, message=msg, logger=logger)


class JailNotSupplied(IocageException):
    """Raised when no jail was supplied."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = f"Please supply a jail"
        IocageException.__init__(self, message=msg, logger=logger)


class JailUnknownIdentifier(IocageException):
    """Raised when the jail has an unknown identifier."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = "The jail has no identifier yet"
        IocageException.__init__(self, message=msg, logger=logger)


class JailBackendMissing(IocageException):
    """Raised when the jails backend was not found."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = "The jail backend is unknown"
        IocageException.__init__(self, message=msg, logger=logger)


class JailIsTemplate(JailException):
    """Raised when the jail is a template but should not be."""

    jail: 'iocage.lib.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The jail '{jail.name}' is a template"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailNotTemplate(JailException):
    """Raised when the jail is no template but should be one."""

    jail: 'iocage.lib.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The jail '{jail.full_name}' is not a template"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailLaunchFailed(JailException):
    """Raised when the jail could not be launched."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Launching jail {jail.full_name} failed"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailDestructionFailed(JailException):
    """Raised when the jail could not be destroyed."""

    jail: 'iocage.lib.Jail.JailGenerator'

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Destroying jail {jail.full_name} failed"
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


class JailCommandFailed(IocageException):
    """Raised when a jail command fails with an exit code > 0."""

    returncode: int

    def __init__(
        self,
        returncode: int,
        logger: typing.Optional[Logger]=None
    ) -> None:
        self.returncode = returncode
        msg = f"Jail command exited with {returncode}"
        IocageException.__init__(self, message=msg, logger=logger)


class JailExecutionAborted(JailException):
    """Raised when a jail command fails with an exit code > 0."""

    def __init__(
        self,
        jail: 'iocage.lib.Jail.JailGenerator',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Jail execution of {jail.humanreadable_name} aborted."
        JailException.__init__(self, message=msg, jail=jail, logger=logger)


# Jail Fstab


class VirtualFstabLineHasNoRealIndex(IocageException):
    """Raised when attempting to access the index of a virtual fstab line."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = f"The virtual fstab line does not have a real list index"
        IocageException.__init__(self, message=msg, logger=logger)


class FstabDestinationExists(IocageException):
    """Raised when the destination directory does not exist."""

    def __init__(
        self,
        mountpoint: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The mountpoint {mountpoint} already exists in the fstab file"
        IocageException.__init__(self, message=msg, logger=logger)


# Security


class SecurityViolation(IocageException):
    """Raised when iocage has security concerns."""

    def __init__(
        self,
        reason: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Security violation: {reason}"
        IocageException.__init__(self, message=msg, logger=logger)


class InsecureJailPath(SecurityViolation):
    """Raised when a a path points outside of a resource."""

    def __init__(
        self,
        path: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Insecure path {path} jail escape attempt"
        SecurityViolation.__init__(self, reason=msg)


class SecurityViolationConfigJailEscape(SecurityViolation):
    """Raised when a file symlinks to a location outside of the jail."""

    def __init__(
        self,
        file: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The file {file} references a file outsite of the jail resource"
        SecurityViolation.__init__(self, reason=msg)


class IllegalArchiveContent(IocageException):
    """Raised when a release asset archive contains malicious content."""

    def __init__(
        self,
        asset_name: str,
        reason: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Asset {asset_name} contains illegal files - {reason}"
        super().__init__(message=msg, logger=logger)


# JailConfig


class JailConfigError(IocageException):
    """Raised when a general configuration error occurs."""

    pass


class InvalidJailName(JailConfigError):
    """Raised when a jail has an invalid name."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = (
            "Invalid jail name: "
            "Names have to begin and end with an alphanumeric character"
        )
        super().__init__(message=msg, logger=logger)


class JailConigZFSIsNotAllowed(JailConfigError):
    """Raised when a jail is not allowed to use ZFS shares."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
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
        jail: typing.Optional[iocage.lib.Jail.JailGenerator]=None,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None,
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
        jail: typing.Optional[iocage.lib.Jail.JailGenerator]=None,
        logger: typing.Optional[Logger]=None,
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


class InvalidMacAddress(IocageException, ValueError):
    """Raised when a jail MAC address is invalid."""

    def __init__(
        self,
        mac_address: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        reason = f"invalid mac address: \"{mac_address}\""
        IocageException.__init__(
            self,
            message=reason
        )


class ResourceLimitUnknown(IocageException, KeyError):
    """Raised when a resource limit has is unknown."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = f"The specified resource limit is unknown"
        IocageException.__init__(self, message=msg, logger=logger)


class JailConfigNotFound(IocageException):
    """Raised when a jail is not configured."""

    def __init__(
        self,
        config_type: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Could not read {config_type} config"
        # This is a silent error internally used
        IocageException.__init__(self, message=msg, logger=logger)


class DefaultConfigNotFound(IocageException, FileNotFoundError):
    """Raised when no default config was found on the host."""

    def __init__(
        self,
        config_file_path: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Default configuration not found at {config_file_path}"
        IocageException.__init__(self, message=msg, logger=logger)


class UnknownJailConfigProperty(IocageException, KeyError):
    """Raised when a unknown jail config property was used."""

    def __init__(
        self,
        key: str,
        jail: iocage.lib.Jail.JailGenerator,
        logger: typing.Optional[Logger]=None,
        level: str="error"
    ) -> None:
        msg = (
            f"The config property '{key}' "
            f"of jail '{jail.humanreadable_name}' is unknown."
        )
        IocageException.__init__(self, message=msg, logger=logger, level=level)


# Backup


class BackupInProgress(IocageException):
    """Raised when a backup operation is already in progress."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:

        msg = "A backup operation is already in progress"
        IocageException.__init__(self, message=msg, logger=logger)


class ExportDestinationExists(IocageException):
    """Raised when a backup operation is already in progress."""

    def __init__(
        self,
        destination: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = "The backup destination {destination} already exists"
        IocageException.__init__(self, message=msg, logger=logger)


# ListableResource


class ListableResourceNamespaceUndefined(IocageException):
    """Raised when a ListableResource was not defined with a namespace."""

    def __init__(
        self,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The ListableResource needs a namespace for this operation"
        IocageException.__init__(self, message=msg, logger=logger)


# General


class IocageNotActivated(IocageException):
    """Raised when iocage is not active on any ZFS pool."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = (
            "iocage is not activated yet - "
            "please run `ioc activate <POOL>` first and select a pool"
        )
        super().__init__(message=msg, logger=logger)


class InvalidLogLevel(IocageException):
    """Raised when the logger was initialized with an invalid log level."""

    def __init__(
        self,
        log_level: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        available_log_levels = iocage.lib.Logger.Logger.LOG_LEVELS
        available_log_levels_string = ", ".join(available_log_levels[:-1])
        msg = (
            f"Invalid log-level {log_level}. Choose one of "
            f"{available_log_levels_string} or {available_log_levels[-1]}"
        )
        super().__init__(message=msg, logger=logger)


class MustBeRoot(IocageException):
    """Raised when iocage is executed without root permission."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        _msg = (
            f"Must be root to {message}"
        )
        super().__init__(message=_msg, logger=logger)


class CommandFailure(IocageException):
    """Raised when iocage fails to execute a command."""

    def __init__(
        self,
        returncode: int,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Command exited with {returncode}"
        super().__init__(message=msg, logger=logger)


class NotAnIocageZFSProperty(IocageException):
    """Raised when iocage attempts to touch a non-iocage ZFS property."""

    def __init__(
        self,
        property_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"The ZFS property '{property_name}' is not managed by iocage"
        super().__init__(message=msg, logger=logger)


# Host, Distribution


class DistributionUnknown(IocageException):
    """Raised when the host distribution is unknown or not supported."""

    def __init__(
        self,
        distribution_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Unknown Distribution: {distribution_name}"
        super().__init__(message=msg, logger=logger)


class HostReleaseUnknown(IocageException):
    """Raised when the host release could not be determined."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = f"The host release is unknown"
        super().__init__(message=msg, logger=logger)


class HostUserlandVersionUnknown(IocageException):
    """Raised when the hosts userland version could not be detected."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = f"Could not determine the hosts userland version"
        super().__init__(message=msg, logger=logger)


class DistributionEOLWarningDownloadFailed(IocageException):
    """Raised when downloading EOL warnings failed."""

    def __init__(
        self,
        logger: typing.Optional[Logger]=None,
        level: str="error"
    ) -> None:
        msg = f"Failed to download the EOL warnings"
        super().__init__(message=msg, logger=logger, level=level)


# Storage


class DatasetExists(IocageException):
    """Raised when a dataset already exists."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Dataset already exists: {dataset_name}"
        super().__init__(message=msg, logger=logger)


class UnmountFailed(IocageException):
    """Raised when an unmount operation fails."""

    def __init__(
        self,
        mountpoint: typing.Any,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Unmount of {mountpoint} failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class MountFailed(IocageException):
    """Raised when a mount operation fails."""

    def __init__(
        self,
        mountpoint: iocage.lib.Types.AbsolutePath,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Failed to mount {mountpoint}"
        super().__init__(message=msg, logger=logger)


class DatasetNotMounted(IocageException):
    """Raised when a dataset is not mounted but should be."""

    def __init__(
        self,
        dataset: 'libzfs.ZFSDataset',
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Dataset '{dataset.name}' is not mounted"
        super().__init__(message=msg, logger=logger)


class DatasetNotAvailable(IocageException):
    """Raised when a dataset is not available."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Dataset '{dataset_name}' is not available"
        super().__init__(message=msg, logger=logger)


class DatasetNotJailed(IocageException):
    """Raised when a ZFS share was not flagged as such."""

    def __init__(
        self,
        dataset: 'libzfs.ZFSDataset',
        logger: typing.Optional[Logger]=None
    ) -> None:

        name = dataset.name
        msg = f"Dataset {name} is not jailed."
        warning = f"Run 'zfs set jailed=on {name}' to allow mounting"
        super().__init__(
            msg,
            warning=warning,
            append_warning=True
        )


class ZFSException(IocageException):
    """Raised when a ZFS pool not available."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        super().__init__(message=message, logger=logger)


class ZFSPoolInvalid(IocageException, TypeError):
    """Raised when a ZFS pool is invalid."""

    def __init__(
        self,
        consequence: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = "Invalid ZFS pool"

        if consequence is not None:
            msg += f": {consequence}"

        IocageException.__init__(self, message=msg, logger=logger)


class ZFSPoolUnavailable(IocageException):
    """Raised when a ZFS pool not available."""

    def __init__(
        self,
        pool_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"ZFS pool '{pool_name}' is UNAVAIL"
        super().__init__(message=msg, logger=logger)


class ResourceUnmanaged(IocageException):
    """Raised when locating a resources dataset on a root dataset fails."""

    def __init__(
        self,
        dataset_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"The resource dataset {dataset_name} is not managed by iocage"
        super().__init__(message=msg, logger=logger)


class ConflictingResourceSelection(IocageException):
    """Raised when a resource was configured with conflicting sources."""

    def __init__(
        self,
        source_a: str,
        source_b: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = (
            "The resource was configured with conflicting root sources: "
            f"{source_a} != {source_b}"
        )
        super().__init__(message=msg, logger=logger)


# Snapshots


class SnapshotError(IocageException):
    """Raised on snapshot related errors."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class SnapshotCreation(SnapshotError):
    """Raised when creating a snapshot failed."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Snapshot not found: {dataset_name}@{snapshot_name}"
        super().__init__(message=msg, logger=logger)


class InvalidSnapshotIdentifier(SnapshotError):
    """Raised when a snapshot identifier is invalid."""

    def __init__(
        self,
        identifier: str,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = (
            f"Invalid snapshot identifier syntax: {identifier}"
            "(should be <jail>@<snapshot>)"
        )
        super().__init__(message=msg, logger=logger)


# Network


class InvalidInterfaceName(IocageException):
    """Raised when a NIC name is invalid."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = "Invalid NIC name"
        super().__init__(message=msg, logger=logger)


class VnetBridgeMissing(IocageException):
    """Raised when a vnet bridge is missing."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = "VNET is enabled and requires setting a bridge"
        super().__init__(message=msg, logger=logger)


class InvalidNetworkBridge(IocageException, ValueError):
    """Raised when a network bridge is invalid."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = "Invalid network bridge argument"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class FirewallDisabled(IocageException):
    """Raised when the firewall is required but disabled (Secure VNET)."""

    def __init__(
        self,
        hint: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = "IPFW is disabled"
        if hint is not None:
            msg += f": {hint}"
        super().__init__(message=msg, logger=logger)


class FirewallCommandFailure(IocageException):
    """Raised when a firewall command fails (Secure VNET)."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        msg = "Firewall Command failed. Is IPFW enabled?"
        super().__init__(message=msg, logger=logger)


class InvalidIPAddress(IocageException):
    """Raised when an invalid IP address was assigned to a network."""

    def __init__(
        self,
        reason: str,
        ipv6: bool,
        logger: typing.Optional[Logger]=None,
        level: str="error"
    ) -> None:
        ip_version = 4 + 2 * (ipv6 is True)
        msg = f"Invalid IPv{ip_version} address: {reason}"
        super().__init__(message=msg, logger=logger, level=level)


# Release


class ReleaseListUnavailable(IocageException):
    """Raised when the list could not be downloaded from the remote."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:

        msg = f"The releases list is unavailable"
        super().__init__(message=msg, logger=logger)


class ReleaseAssetHashesUnavailable(IocageException):
    """Raised when the list could not be downloaded from the remote."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:

        msg = f"The releases asset hashes are unavailable"
        super().__init__(message=msg, logger=logger)


class UpdateFailure(IocageException):
    """Raised when an update fails."""

    def __init__(
        self,
        name: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Release update of '{name}' failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


class InvalidReleaseAssetSignature(UpdateFailure):
    """Raised when a release signature is invalid."""

    def __init__(
        self,
        name: str,
        asset_name: str,
        logger: typing.Optional[Logger]=None
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
        resource: 'iocage.lib.Resource.Resource',
        logger: typing.Optional[Logger]=None
    ) -> None:

        msg = f"Updates can only be fetched for releases"
        UpdateFailure.__init__(
            self,
            name=resource.name,
            reason=msg
        )


class ReleaseNotFetched(IocageException):
    """Raised when a release was not yet fetched."""

    def __init__(
        self,
        name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Release '{name}' does not exist or is not fetched locally"
        super().__init__(message=msg, logger=logger)


class ReleaseUpdateBranchLookup(IocageException):
    """Raised when failing to lookup the remote update branch."""

    def __init__(
        self,
        release_name: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
    ) -> None:
        feature_name = f"Support for release version {version}"
        super().__init__(
            feature_name=feature_name,
            plural=True
        )


class InvalidReleaseName(IocageException):
    """Raised when interacting with an unsupported release."""

    def __init__(
        self,
        name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Invalid release name: {name}"
        super().__init__(message=msg, logger=logger)


# Prompts


class DefaultReleaseNotFound(IocageException):
    """Raised when the default (host) release does not match a remote."""

    def __init__(
        self,
        host_release_name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = (
            f"Release '{host_release_name}' not found: "
            "Could not determine a default source"
        )
        super().__init__(message=msg, logger=logger)


# DevfsRules


class DevfsRuleException(IocageException):
    """Raised on errors in devfs rules."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class InvalidDevfsRulesSyntax(DevfsRuleException):
    """Raised when a devfs rule has invalid syntax."""

    def __init__(
        self,
        devfs_rules_file: str,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
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
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = "The devfs ruleset is missing a name"
        super().__init__(message=msg, logger=logger)

# Logger


class LogException(IocageException):
    """Raised when logging fails."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        super().__init__(message=message, logger=logger)


class CannotRedrawLine(LogException):
    """Raised when manipulating previous log entries fails."""

    def __init__(
        self,
        reason: typing.Optional[str]=None,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = "Logger can't redraw line"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(message=msg, logger=logger)


# Events


class EventAlreadyFinished(IocageException):
    """Raised when a event is touched that was already finished."""

    def __init__(
        self,
        event: 'iocage.lib.events.IocageEvent',
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = "This {event.type} event is already finished"
        IocageException.__init__(self, message=msg, logger=logger)


# Jail Filter


class JailFilterException(IocageException):
    """Raised when a jail filter is invalid."""

    def __init__(
        self,
        message: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        IocageException.__init__(self, message=message, logger=logger)


class JailFilterInvalidName(JailFilterException):
    """Raised when the name of a jail filter is invalid."""

    def __init__(self, logger: typing.Optional[Logger]=None) -> None:
        message = (
            "Invalid jail selector: "
            "Cannot select jail with illegal name"
        )
        JailFilterException.__init__(self, message=message, logger=logger)


# pkg


class PkgNotFound(IocageException):
    """Raised when the pkg package was not found in the local mirror."""

    def __init__(
        self,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = "The pkg package was not found in the local mirror."
        IocageException.__init__(self, message=msg, logger=logger)


# Provisioning


class UnknownProvisioner(IocageException):
    """Raised when an unsupported provisioner method is used."""

    def __init__(
        self,
        name: str,
        logger: typing.Optional[Logger]=None
    ) -> None:
        msg = f"Unknown provisioner: {name}"
        IocageException.__init__(self, message=msg, logger=logger)
