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
"""iocage provisioning prototype."""
import typing

import libioc.errors
import libioc.helpers
import libioc.Provisioning.ix


class Prototype:

	jail: 'libioc.Jail.JailGenerator'
	__METHOD: str

	def __init__(
		self,
		jail: 'libioc.Jail.JailGenerator'
	) -> None:
		self.jail = jail

	@property
	def method(self) -> str:
		self.__METHOD

	@property
	def source(self) -> typing.Optional[str]:
		config_value = self.jail.config["provisioning.source"]
		return None if (config_value is None) else str(config_value)

	@property
	def rev(self) -> typing.Optional[str]:
		config_value = self.jail.config["provisioning.rev"]
		return None if (config_value is None) else str(config_value)

	def check_requirements(self) -> None:
		"""Check requirements before executing the provisioner."""
		if self.source is None:
			raise libioc.errors.UndefinedProvisionerSource(
				logger=self.jail.logger
			)
		if self.method is None:
			raise libioc.errors.UndefinedProvisionerMethod(
				logger=self.jail.logger
			)


class Provisioner(Prototype):

	@property
	def method(self) -> str:
		method = self.jail.config["provisioning.method"]
		if method in self.__available_provisioning_modules:
			return method
		raise libioc.errors.InvalidProvisionerMethod(
			method,
			logger=self.jail.logger
		)

	@property
	def __available_provisioning_modules(
		self
	) -> typing.Dict[str, Prototype]:
		return dict(
			ix=libioc.Provisioning.ix
		)

	@property
	def __provisioning_module(self) -> 'libioc.Provisioning.Provisioner':
		"""Return the class of the currently configured provisioner."""
		return self.__available_provisioning_modules[self.method]

	def provision(
		self
	) -> typing.Generator['libioc.events.IocEvent', None, None]:
		"""Run the provision method on the enabled provisioner."""
		Prototype.check_requirements(self)
		yield from self.__provisioning_module.provision(self)
