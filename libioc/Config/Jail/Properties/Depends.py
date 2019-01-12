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
"""Jail config depends property."""
import typing

import libioc.helpers
import libioc.Filter


class DependsProp(libioc.Filter.Terms):
    """Special jail config property Depends."""

    config: 'libioc.Config.Jail.JailConfig.JailConfig'
    property_name: str
    logger: typing.Optional['libioc.Logger.Logger']
    delimiter: str = ","

    def __init__(
        self,
        config: typing.Optional[
            'libioc.Config.Jail.JailConfig.JailConfig'
        ]=None,
        property_name: str="depends",
        logger: typing.Optional['libioc.Logger.Logger']=None
    ) -> None:
        self.property_name = property_name
        self.logger = logger
        if config is not None:
            self.config = config
        libioc.Filter.Terms.__init__(self, logger=logger)

    def set(
        self,
        data: typing.Optional[typing.Union[
            str,
            typing.Iterable[typing.Union[libioc.Filter.Term, str]]
        ]],
        skip_on_error: bool=False
    ) -> None:
        """Clear and set all terms from input data."""
        try:
            libioc.Filter.Terms.set(
                self,
                terms=data
            )
        except libioc.errors.IocException:
            if skip_on_error is False:
                raise

        self.__notify()

    def add(
        self,
        term: typing.Union[libioc.Filter.Term, str],
        notify: typing.Optional[bool]=True
    ) -> None:
        """
        Add a Filter.Term to the depends Jail Config property.

        Args:

            term (libioc.Filter.Term, str):
                Depends Filter.Term to add

            notify (bool): (default=True)
                Sends an update notification to the jail config instance
        """
        libioc.Filter.Terms.add(self, term)
        if notify is True:
            self.__notify()

    def __delitem__(self, key: typing.Any) -> None:
        """Remove a jail dependency."""
        dict.__delitem__(self, key)
        self.__notify()

    def __notify(self) -> None:
        self.config.update_special_property(self.property_name)

    def __empty_prop(self, key: str) -> None:
        dict.__setitem__(self, key, None)
