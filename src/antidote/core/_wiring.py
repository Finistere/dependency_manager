import inspect
from typing import Callable, Dict, TypeVar, Union, cast

from .exceptions import DoubleInjectionError
from .injection import inject
from .wiring import Methods, Wiring
from .._internal import API
from .._internal.wrapper import is_wrapper

C = TypeVar('C', bound=type)
AnyF = Union[Callable[..., object], staticmethod, classmethod]


@API.private
def wire_class(cls: C, wiring: Wiring) -> C:
    if not (isinstance(cls, type) and inspect.isclass(cls)):
        raise TypeError(f"Expecting a class, got a {type(cls)}")

    methods: Dict[str, AnyF] = dict()
    if isinstance(wiring.methods, Methods):
        assert wiring.methods is Methods.ALL  # Sanity check
        for name, member in cls.__dict__.items():
            if (name in {'__call__', '__init__'}
                    or not (name.startswith("__") and name.endswith("__"))):
                if (inspect.isfunction(member)
                        or is_wrapper(member)  # we may need to raise DoubleInjectionError
                        or isinstance(member, (staticmethod, classmethod))):
                    methods[name] = cast(AnyF, member)
    else:
        for method_name in wiring.methods:
            try:
                attr = cls.__dict__[method_name]
            except KeyError as e:
                raise AttributeError(method_name) from e

            if not (callable(attr)
                    or isinstance(attr, (staticmethod, classmethod))):
                raise TypeError(f"{method_name} is not a (static/class) method. "
                                f"Found: {type(attr)}")
            methods[method_name] = cast(AnyF, attr)

    for name, method in methods.items():
        try:
            injected_method = inject(
                method,
                dependencies=wiring.dependencies,
                use_names=wiring.use_names,
                auto_provide=wiring.auto_provide,
                strict_validation=False
            )
        except DoubleInjectionError:
            if wiring.raise_on_double_injection:
                raise
        else:
            if injected_method is not method:  # If something has changed
                setattr(cls, name, injected_method)

    return cls
