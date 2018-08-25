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
"""Collection of iocage helper functions used in objects."""
import typing

import iocage.Logger


def init_zfs(
    self: typing.Any,
    zfs: typing.Optional['iocage.ZFS.ZFS']=None
) -> 'iocage.ZFS.ZFS':
    """Attach or initialize a ZFS object."""
    try:
        return self.zfs
    except AttributeError:
        pass

    import iocage.ZFS
    if (zfs is not None) and isinstance(zfs, iocage.ZFS.ZFS):
        object.__setattr__(self, 'zfs', zfs)
    else:
        new_zfs = iocage.ZFS.get_zfs(logger=self.logger)
        object.__setattr__(self, 'zfs', new_zfs)

    return object.__getattribute__(self, 'zfs')


def init_host(
    self: typing.Any,
    host: typing.Optional['iocage.Host.HostGenerator']=None
) -> 'iocage.Host.HostGenerator':
    """Attach or initialize a Host object."""
    try:
        return self.host
    except AttributeError:
        pass

    import iocage.Host
    if (host is not None) and isinstance(host, iocage.Host.HostGenerator):
        return host

    return iocage.Host.HostGenerator(
        logger=self.logger,
        zfs=self.zfs
    )


def init_distribution(
    self: typing.Any,
    distribution: typing.Optional['iocage.Distribution.Distribution']=None
) -> 'iocage.Distribution.DistributionGenerator':
    """Attach or initialize a Distribution object."""
    try:
        return self.distribution
    except AttributeError:
        pass

    import iocage.Distribution

    if (distribution is not None):
        if isinstance(distribution, iocage.Distribution.DistributionGenerator):
            return distribution

    return iocage.Distribution.Distribution(
        logger=self.logger,
        zfs=self.zfs
    )


def init_logger(
    self: typing.Any,
    logger: typing.Optional['iocage.Logger.Logger']=None
) -> 'iocage.Logger.Logger':
    """Attach or initialize a Logger object."""
    try:
        return self.logger
    except AttributeError:
        pass

    if logger is not None:
        object.__setattr__(self, 'logger', logger)
        return logger
    else:
        try:
            return self.logger
        except AttributeError:
            new_logger = iocage.Logger.Logger()
            object.__setattr__(self, 'logger', new_logger)
            return new_logger
