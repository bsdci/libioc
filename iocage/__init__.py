import sys
import importlib
import typing


class _HookedModule:

	def __call__(self, *args, **kwargs) -> None:
		name = self.__name__
		main_module = sys.modules[name].__getattribute__(name.split(".").pop())
		return main_module(*args, **kwargs)		

	def __instancecheck__(self, target_class) -> bool:
		import pdb; pdb.set_trace()

def hook_module(module_name: str, hooked_submodule_names: typing.List[str]):

	class _IocageModule(sys.modules["iocage"].__class__, _HookedModule):

		hooked_modules = hooked_submodule_names

		def __getattribute__(self, key: str) -> typing.Any:
			if key.startswith("_") is True:
				return super().__getattribute__(key)

			try:
				method = super().__getattribute__(key)
				if callable(method) is True:
					return method
			except AttributeError:
				pass

			if key in object.__getattribute__(self, "hooked_modules"):
				if key not in sys.modules.keys():
					self.__load_hooked_module(key)
				elif not isinstance(sys.modules[name], _HookedModule):
					import pdb; pdb.set_trace()
					sys.modules[name] = self._hook_module(sys.modules)
			else:
				self.__load_module(key)

			return super().__getattribute__(key)

		def __load_module(self, name: str) -> None:
			module = importlib.import_module(f"{module_name}.{name}")
			sys.modules[name] = module

		def __load_hooked_module(self, name: str) -> None:
			module = importlib.import_module(f"{module_name}.{name}")
			sys.modules[name] = self.__hook_module(module)

		def __hook_module(self, module: typing.Any) -> None:

			class _Module(module.__class__, _HookedModule):

				pass

			module.__class__ = _Module
			return module


	sys.modules[module_name].__class__ = _IocageModule


hook_module(
	module_name="iocage",
	hooked_submodule_names=[
		"Host",
		"Distribution",
		"Jails",
		"Jail",
		"Releases",
		"Release"
	]
)