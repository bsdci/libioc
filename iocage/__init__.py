import sys
import importlib
import typing


class HookedModule:

	def __call__(self, *args, **kwargs) -> None:
		return self.main_module(*args, **kwargs)

	@property
	def main_module(self) -> typing.Any:
		name = self.__name__
		return sys.modules[name].__getattribute__(name.split(".").pop())


class IocageModule(sys.modules["iocage"].__class__):

	hooked_modules = [
		"Host",
		"Distribution",
		"Jails",
		"Jail",
		"Releases",
		"Release"
	]

	def __getattribute__(self, key: str) -> typing.Any:
		if key.startswith("_") is True:
			return super().__getattribute__(key)

		if key not in sys.modules.keys():
			if key in object.__getattribute__(self, "hooked_modules"):
				self.__load_hooked_module(key)
			else:
				self.__load_module(key)
		return super().__getattribute__(key)

	def __load_module(self, name: str) -> None:
		module = importlib.import_module(f"iocage.{name}")
		sys.modules[name] = module

	def __load_hooked_module(self, name: str) -> None:
		module = importlib.import_module(f"iocage.{name}")
		sys.modules[name] = self.__hook_module(module)

	def __hook_module(self, module: typing.Any) -> None:

		class _HookedModule(module.__class__, HookedModule):

			pass


		module.__class__ = _HookedModule
		return module


sys.modules["iocage"].__class__ = IocageModule
