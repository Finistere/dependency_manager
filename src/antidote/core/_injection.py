import collections.abc as c_abc
import inspect
from typing import (Any, Callable, cast, Dict, Hashable, Iterable, Mapping, overload,
                    Set, TYPE_CHECKING, TypeVar, Union, List)

from .exceptions import DoubleInjectionError
from .._internal import API
from .._internal.argspec import Arguments
from .._internal.wrapper import (build_wrapper, get_wrapped, Injection,
                                 InjectionBlueprint, is_wrapper)

if TYPE_CHECKING:
    from .injection import DEPENDENCIES_TYPE

F = TypeVar('F', bound=Callable[..., Any])
AnyF = Union[Callable[..., Any], staticmethod, classmethod]


@overload
def raw_inject(func: staticmethod,  # noqa: E704  # pragma: no cover
               *,
               arguments: Arguments = None,
               dependencies: 'DEPENDENCIES_TYPE' = None,
               use_names: Union[bool, Iterable[str]] = None,
               use_type_hints: Union[bool, Iterable[str]] = None
               ) -> staticmethod: ...


@overload
def raw_inject(func: classmethod,  # noqa: E704  # pragma: no cover
               *,
               arguments: Arguments = None,
               dependencies: 'DEPENDENCIES_TYPE' = None,
               use_names: Union[bool, Iterable[str]] = None,
               use_type_hints: Union[bool, Iterable[str]] = None
               ) -> classmethod: ...


@overload
def raw_inject(func: F,  # noqa: E704  # pragma: no cover
               *,
               arguments: Arguments = None,
               dependencies: 'DEPENDENCIES_TYPE' = None,
               use_names: Union[bool, Iterable[str]] = None,
               use_type_hints: Union[bool, Iterable[str]] = None
               ) -> F: ...


@overload
def raw_inject(*,  # noqa: E704  # pragma: no cover
               arguments: Arguments = None,
               dependencies: 'DEPENDENCIES_TYPE' = None,
               use_names: Union[bool, Iterable[str]] = None,
               use_type_hints: Union[bool, Iterable[str]] = None
               ) -> Callable[[F], F]: ...


@API.private  # Use inject instead
def raw_inject(func: AnyF = None,
               *,
               arguments: Arguments = None,
               dependencies: 'DEPENDENCIES_TYPE' = None,
               use_names: Union[bool, Iterable[str]] = None,
               use_type_hints: Union[bool, Iterable[str]] = None
               ) -> AnyF:
    def _inject(f: AnyF) -> AnyF:
        if inspect.isclass(f):
            # @inject on a class would not return a class which is
            # counter-intuitive.
            raise TypeError("Classes cannot be wrapped with @inject. "
                            "Consider using @wire")
        if not (callable(f) or isinstance(f, (classmethod, staticmethod))):
            raise TypeError(f"wrapped object {f} is neither a callable "
                            f"nor a class/static method")

        real_f = f.__func__ if isinstance(f, (classmethod, staticmethod)) else f
        if is_wrapper(f):
            raise DoubleInjectionError(get_wrapped(f))
        if is_wrapper(real_f):
            raise DoubleInjectionError(get_wrapped(real_f))

        blueprint = _build_injection_blueprint(
            arguments=Arguments.from_callable(f) if arguments is None else arguments,
            dependencies=dependencies,
            use_names=use_names,
            use_type_hints=use_type_hints
        )
        # If nothing can be injected, just return the existing function without
        # any overhead.
        if blueprint.is_empty():
            return f

        wrapped_real_f = build_wrapper(blueprint=blueprint, wrapped=real_f)
        if isinstance(f, staticmethod):
            return staticmethod(wrapped_real_f)
        if isinstance(f, classmethod):
            return classmethod(wrapped_real_f)
        return cast(AnyF, wrapped_real_f)

    return func and _inject(func) or _inject


@API.private
def _build_injection_blueprint(arguments: Arguments,
                               dependencies: 'DEPENDENCIES_TYPE' = None,
                               use_names: Union[bool, Iterable[str]] = None,
                               use_type_hints: Union[bool, Iterable[str]] = None,
                               ) -> InjectionBlueprint:
    """
    Construct a InjectionBlueprint with all the necessary information about
    the arguments for dependency injection. Storing it avoids significant
    execution overhead./

    Used by inject()
    """
    from .annotations import IGNORE_SENTINEL
    use_names = use_names if use_names is not None else False
    use_type_hints = use_type_hints if use_type_hints is not None else True

    arg_to_dependency = _build_arg_to_dependency(arguments, dependencies)
    type_hints = _build_type_hints(arguments, use_type_hints)
    dependency_names = _build_dependency_names(arguments, use_names)
    resolved_dependencies: List[object] = []

    for arg in arguments:
        d = type_hints.get(arg.name,
                           arg.name if arg.name in dependency_names else None)
        # Specifying explicitly Ignore in the type_hints has priority over
        # everything else.
        if d is IGNORE_SENTINEL:
            resolved_dependencies.append(None)
        else:
            resolved_dependencies.append(arg_to_dependency.get(arg.name, d))

    return InjectionBlueprint(tuple(
        Injection(arg_name=arg.name,
                  required=not arg.has_default,
                  dependency=dependency)
        for arg, dependency in zip(arguments, resolved_dependencies)
    ))


@API.private
def _build_arg_to_dependency(arguments: Arguments,
                             dependencies: 'DEPENDENCIES_TYPE' = None
                             ) -> Dict[str, Hashable]:
    from .injection import Arg
    if dependencies is None:
        arg_to_dependency: Mapping[str, Hashable] = {}
    elif isinstance(dependencies, str):
        if "{arg_name}" not in dependencies:
            raise ValueError("Missing formatting parameter {arg_name} in dependencies.")
        arg_to_dependency = {arg.name: dependencies.format(arg_name=arg.name)
                             for arg in arguments.without_self}
    elif callable(dependencies):
        arg_to_dependency = {arg.name: dependencies(Arg(arg.name,
                                                        arg.type_hint,
                                                        arg.type_hint_with_extras))
                             for arg in arguments.without_self}
    elif isinstance(dependencies, c_abc.Mapping):
        _check_valid_arg_names(dependencies.keys(), arguments)
        arg_to_dependency = dependencies
    elif isinstance(dependencies, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        dependencies = tuple(dependencies)
        if len(arguments.without_self) < len(dependencies):
            raise ValueError(f"More dependencies ({dependencies}) were provided "
                             f"than arguments ({arguments})")
        arg_to_dependency = {arg.name: dependency
                             for arg, dependency
                             in zip(arguments.without_self, dependencies)}
    else:
        raise TypeError(f'Only a mapping or a iterable is supported for '
                        f'dependencies, not {type(dependencies)!r}')

    # Remove any None as they would hide type_hints and use_names.
    return {k: v for k, v in arg_to_dependency.items() if v is not None}


@API.private
def _build_type_hints(arguments: Arguments,
                      use_type_hints: Union[bool, Iterable[str]]) -> Dict[str, Hashable]:
    from .annotations import extract_argument_dependency

    if use_type_hints is True:
        type_hints = {arg.name: arg.type_hint for arg in arguments.without_self}
    elif use_type_hints is False:
        return {}
    elif isinstance(use_type_hints, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        use_type_hints = tuple(use_type_hints)
        _check_valid_arg_names(use_type_hints, arguments)

        type_hints = {name: arguments[name].type_hint for name in use_type_hints}

    else:
        raise TypeError(f"Only an iterable or a boolean is supported for "
                        f"use_type_hints, not {type(use_type_hints)!r}")

    arg_to_dependency = {}
    for arg_name in list(type_hints.keys()):
        dependency = extract_argument_dependency(arguments[arg_name])
        if dependency is not None:
            arg_to_dependency[arg_name] = dependency

    return arg_to_dependency


@API.private
def _build_dependency_names(arguments: Arguments,
                            use_names: Union[bool, Iterable[str]]) -> Set[str]:
    if use_names is False:
        return set()
    elif use_names is True:
        return {arg.name for arg in arguments.without_self}
    elif isinstance(use_names, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        use_names = tuple(use_names)
        _check_valid_arg_names(use_names, arguments)
        return set(use_names)
    else:
        raise TypeError(f'Only an iterable or a boolean is supported for '
                        f'use_names, not {type(use_names)!r}')


@API.private
def _check_valid_arg_names(names: Iterable[str], arguments: Arguments) -> None:
    for name in names:
        if not isinstance(name, str):
            raise TypeError(f"Expected argument name (str), "
                            f"not {type(name)}")
        if name not in arguments:
            raise ValueError(f"Unknown argument '{name}'")
        if arguments.has_self and name == arguments[0].name:
            raise ValueError(f"Cannot inject first argument "
                             f"('{arguments[0]}') of a method")
