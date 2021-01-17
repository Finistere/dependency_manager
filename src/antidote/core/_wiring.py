import collections.abc as c_abc
import inspect
from typing import Callable, TypeVar, Union, cast

from ._injection import raw_inject
from .exceptions import DoubleInjectionError
from .injection import inject
from .wiring import Wiring
from .._internal import API
from .._internal.argspec import Arguments

C = TypeVar('C', bound=type)
AnyF = Union[Callable[..., object], staticmethod, classmethod]


@API.private
def wire_class(cls: C, wiring: Wiring) -> C:
    if not (isinstance(cls, type) and inspect.isclass(cls)):
        raise TypeError(f"Expecting a class, got a {type(cls)}")

    for method_name in wiring.methods:
        try:
            attr = cls.__dict__[method_name]
        except KeyError as e:
            raise AttributeError(method_name)

        if not (callable(attr) or isinstance(attr, (staticmethod, classmethod))):
            raise TypeError(f"{method_name} is neither a method,"
                            f" nor a static/class method. Found: {type(attr)}")

        method = cast(AnyF, attr)
        arguments = Arguments.from_callable(method)
        use_names = wiring.use_names
        use_type_hints = wiring.use_type_hints
        dependencies = wiring.dependencies

        # Restrict injection parameters to those really needed by the method.
        if isinstance(dependencies, c_abc.Mapping):
            dependencies = {
                arg_name: dependency
                for arg_name, dependency in dependencies.items()
                if arg_name in arguments.without_self
            }
        elif isinstance(dependencies, c_abc.Sequence) \
                and not isinstance(dependencies, str):
            dependencies = dependencies[:len(arguments.without_self)]

        if not isinstance(use_names, bool):
            use_names = use_names.intersection(arguments.arg_names)

        if not isinstance(use_type_hints, bool):
            use_type_hints = use_type_hints.intersection(arguments.arg_names)

        injected_method = raw_inject(
            method,
            arguments=arguments,
            dependencies=dependencies,
            use_names=use_names,
            use_type_hints=use_type_hints
        )
        if injected_method is not method:  # If something has changed
            setattr(cls, method_name, injected_method)

    for name, member in cls.__dict__.items():
        if (name in {'__call__', '__init__'}
                or not (name.startswith("__") and name.endswith("__"))):
            if inspect.isroutine(member):
                method = cast(AnyF, member)
                try:
                    injected_method = inject(method)
                except DoubleInjectionError:
                    pass
                else:
                    if injected_method is not method:  # If something has changed
                        setattr(cls, name, injected_method)

    return cls
