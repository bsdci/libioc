# Copyright (c) 2014-2017, iocage
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


class IocageException(Exception):

    def __init__(self, message, errors=None, logger=None, level="error",
                 append_warning=False, warning=None):
        if logger is not None:
            logger.__getattribute__(level)(message)
            if append_warning is True:
                logger.warn(warning)
        if errors is not None:
            super().__init__(message, errors)
        else:
            super().__init__(message)


# Jails


class JailDoesNotExist(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' does not exist"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailAlreadyExists(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' already exists"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailNotRunning(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' is not running"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailAlreadyRunning(IocageException):

    def __init__(self, jail, *args, **kwargs):
        msg = f"Jail '{jail.humanreadable_name}' is already running"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailNotFound(IocageException):

    def __init__(self, text, *args, **kwargs):
        msg = f"No jail matching '{text}' was found"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailNotSupplied(IocageException):

    def __init__(self, *args, **kwargs):
        msg = f"Please supply a jail"
        IocageException.__init__(self, msg, *args, **kwargs)


class JailUnknownIdentifier(IocageException):

    def __init__(self, *args, **kwargs):
        msg = "The jail has no identifier yet"
        IocageException.__init__(self, msg, *args, **kwargs)

# JailConfig


class JailConfigError(IocageException):
    pass


class InvalidJailName(JailConfigError):

    def __init__(self, *args, **kwargs):
        msg = (
            "Invalid jail name: "
            "Names have to begin and end with an alphanumeric character"
        )
        super().__init__(msg, *args, **kwargs)


class JailConigZFSIsNotAllowed(JailConfigError):

    def __init__(self, *args, **kwargs):
        msg = (
            "jail_zfs is disabled"
            "despite jail_zfs_dataset is configured"
        )
        super().__init__(msg, *args, **kwargs)


class InvalidJailConfigValue(JailConfigError):

    def __init__(self, property_name, jail=None, reason=None, **kwargs):
        msg = f"Invalid value for property '{property_name}'"
        if jail is not None:
            msg += f" of jail {jail.humanreadable_name}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, **kwargs)


class InvalidJailConfigAddress(InvalidJailConfigValue):

    def __init__(self, value, **kwargs):
        reason = f"expected \"<nic>|<address>\" but got \"{value}\""
        super().__init__(
            reason=reason,
            **kwargs
        )


class JailConfigNotFound(IocageException):

    def __init__(self, config_type, *args, **kwargs):
        msg = f"Could not read {config_type} config"
        # This is a silent error internally used
        Exception.__init__(self, msg, *args, **kwargs)


class DefaultConfigNotFound(IocageException, FileNotFoundError):

    def __init__(self, config_file_path, *args, **kwargs):
        msg = f"Default configuration not found at {config_file_path}"
        IocageException.__init__(self, msg, *args, **kwargs)


# General


class IocageNotActivated(IocageException):

    def __init__(self, *args, **kwargs):
        msg = (
            "iocage is not activated yet - "
            "please run `iocage activate` first and select a pool"
        )
        super().__init__(msg, *args, **kwargs)


class MustBeRoot(IocageException):

    def __init__(self, msg, *args, **kwargs):
        _msg = (
            f"Must be root to {msg}"
        )
        super().__init__(_msg, *args, **kwargs)


class CommandFailure(IocageException):

    def __init__(self, returncode, *args, **kwargs):
        msg = f"Command exited with {returncode}"
        super().__init__(msg, *args, **kwargs)


# Host, Distribution


class DistributionUnknown(IocageException):

    def __init__(self, distribution_name, *args, **kwargs):
        msg = f"Unknown Distribution: {distribution_name}"
        super().__init__(msg, *args, **kwargs)


# Storage


class UnmountFailed(IocageException):

    def __init__(self, mountpoint, *args, **kwargs):
        msg = f"Failed to unmount {mountpoint}"
        super().__init__(msg, *args, **kwargs)


class MountFailed(IocageException):

    def __init__(self, mountpoint, *args, **kwargs):
        msg = f"Failed to mount {mountpoint}"
        super().__init__(msg, *args, **kwargs)


class DatasetNotMounted(IocageException):

    def __init__(self, dataset, *args, **kwargs):
        msg = f"Dataset '{dataset.name}' is not mounted"
        super().__init__(msg, *args, **kwargs)


class DatasetNotAvailable(IocageException):

    def __init__(self, dataset_name, *args, **kwargs):
        msg = f"Dataset '{dataset_name}' is not available"
        super().__init__(msg, *args, **kwargs)


class DatasetNotJailed(IocageException):

    def __init__(self, dataset, *args, **kwargs):
        name = dataset.name
        msg = f"Dataset {name} is not jailed."
        warning = f"Run 'zfs set jailed=on {name}' to allow mounting"
        kwargs["append_warning"] = warning
        super().__init__(msg, *args, **kwargs)


class ZFSPoolInvalid(IocageException, TypeError):

    def __init__(self, consequence=None, *args, **kwargs):
        msg = "Invalid ZFS pool"

        if consequence is not None:
            msg += f": {consequence}"

        IocageException.__init__(self, msg, *args, **kwargs)


class ZFSPoolUnavailable(IocageException):

    def __init__(self, pool_name, *args, **kwargs):
        msg = f"ZFS pool '{pool_name}' is UNAVAIL"
        super().__init__(msg, *args, **kwargs)


# Network


class VnetBridgeMissing(IocageException):

    def __init__(self, *args, **kwargs):
        msg = "VNET is enabled and requires setting a bridge"
        super().__init__(msg, *args, **kwargs)


class InvalidNetworkBridge(IocageException, ValueError):

    def __init__(self, reason=None, *args, **kwargs):
        msg = "Invalid network bridge argument"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


# Release


class UnknownReleasePool(IocageException):

    def __init__(self, *args, **kwargs):
        msg = (
            "Cannot determine the ZFS pool without knowing"
            "the dataset or root_dataset"
        )
        super().__init__(msg, *args, **kwargs)


class ReleaseUpdateFailure(IocageException):

    def __init__(self, release_name, reason=None, *args, **kwargs):
        msg = f"Release update of '{release_name}' failed"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


class InvalidReleaseAssetSignature(ReleaseUpdateFailure):

    def __init__(self, release_name, asset_name, *args, **kwargs):
        msg = f"Asset {asset_name} has an invalid signature"
        super().__init__(release_name, reason=msg, *args, **kwargs)


class IllegalReleaseAssetContent(ReleaseUpdateFailure):

    def __init__(self, release_name, asset_name, reason, *args, **kwargs):
        msg = f"Asset {asset_name} contains illegal files - {reason}"
        super().__init__(release_name, reason=msg, *args, **kwargs)


class ReleaseNotFetched(IocageException):

    def __init__(self, name, *args, **kwargs):
        msg = f"Release '{name}' does not exist or is not fetched locally"
        super().__init__(msg, *args, **kwargs)


class ReleaseUpdateBranchLookup(IocageException):

    def __init__(self, release_name, reason=None, *args, **kwargs):
        msg = f"Update source of release '{release_name}' not found"
        if reason is not None:
            msg += ": {reason}"
        super.__init__(msg, *args, **kwargs)


# Prompts


class DefaultReleaseNotFound(IocageException):

    def __init__(self, host_release_name, *args, **kwargs):
        msg = (
            f"Release '{host_release_name}' not found: "
            "Could not determine a default source"
        )
        super().__init__(msg, *args, **kwargs)


# DevfsRules


class DevfsRuleException(IocageException):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class InvalidDevfsRulesSyntax(DevfsRuleException):

    def __init__(self, devfs_rules_file, reason=None, *args, **kwargs):
        msg = f"Invalid devfs rules in {devfs_rules_file}"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


class DuplicateDevfsRuleset(DevfsRuleException):

    def __init__(self, devfs_rules_file, reason=None, *args, **kwargs):
        msg = "Cannot add duplicate ruleset"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


# Logger


class LogException(IocageException):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CannotRedrawLine(LogException):

    def __init__(self, reason, *args, **kwargs):
        msg = "Logger can't redraw line"
        if reason is not None:
            msg += f": {reason}"
        super().__init__(msg, *args, **kwargs)


# Events


class EventAlreadyFinished(IocageException):

    def __init__(self, event, *args, **kwargs):
        msg = "This {event.type} event is already finished"
        IocageException.__init__(self, msg, *args, **kwargs)


# Jail Filter


class JailFilterException(IocageException):

    def __init__(self, *args, **kwargs):
        IocageException.__init__(self, *args, **kwargs)


class JailFilterInvalidName(JailFilterException):

    def __init__(self, *args, **kwargs):
        msg = (
            "Invalid jail selector: "
            "Cannot select jail with illegal name"
        )
        JailFilterException.__init__(self, msg, *args, **kwargs)


# Missing Features


class MissingFeature(IocageException, NotImplementedError):

    def __init__(
            self,
            feature_name: str,
            plural: bool=False,
            *args,
            **kwargs
    ) -> None:
        message = (
            f"Missing Feature: '{feature_name}' "
            "are" if plural is True else "is"
            " not implemented yet"
        )
        IocageException.__init__(self, message, *args, **kwargs)
