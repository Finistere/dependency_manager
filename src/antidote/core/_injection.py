import collections.abc as c_abc
import inspect
from typing import (Any, Callable, Dict, Hashable, Iterable, List, Mapping, Set,
                    TYPE_CHECKING, Union, cast)

from .exceptions import DoubleInjectionError
from .._internal import API
from .._internal.argspec import Arguments
from .._internal.utils import YesSet
from .._internal.wrapper import (Injection, InjectionBlueprint, build_wrapper,
                                 get_wrapped, is_wrapper)

if TYPE_CHECKING:
    from .injection import DEPENDENCIES_TYPE

AnyF = Union[Callable[..., Any], staticmethod, classmethod]


@API.private
def raw_inject(f: AnyF,
               dependencies: 'DEPENDENCIES_TYPE',
               use_names: Union[bool, Iterable[str]],
               auto_provide: Union[bool, Iterable[Hashable]],
               strict_validation: bool) -> AnyF:
    if not isinstance(strict_validation, bool):
        raise TypeError(f"strict_validation must be a boolean, "
                        f"not {type(strict_validation)}")
    if inspect.isclass(f):
        # User-friendlier error for classes.
        raise TypeError("Classes cannot be wrapped with @inject. "
                        "Consider using @wire")

    real_f = f.__func__ if isinstance(f, (classmethod, staticmethod)) else f
    if is_wrapper(f):
        raise DoubleInjectionError(get_wrapped(f))
    if is_wrapper(real_f):
        raise DoubleInjectionError(get_wrapped(real_f))
    if not inspect.isfunction(real_f):
        raise TypeError(f"wrapped object {f} is neither a function "
                        f"nor a (class/static) method")

    blueprint = _build_injection_blueprint(
        arguments=Arguments.from_callable(f),
        dependencies=dependencies,
        use_names=use_names,
        auto_provide=auto_provide,
        strict_validation=strict_validation
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


@API.private
def _build_injection_blueprint(arguments: Arguments,
                               dependencies: 'DEPENDENCIES_TYPE',
                               use_names: Union[bool, Iterable[str]],
                               auto_provide: Union[bool, Iterable[Hashable]],
                               strict_validation: bool
                               ) -> InjectionBlueprint:
    """
    Construct a InjectionBlueprint with all the necessary information about
    the arguments for dependency injection. Storing it avoids significant
    execution overhead./

    Used by inject()
    """
    annotated = _build_from_annotations(arguments)
    explicit_dependencies = _build_from_dependencies(arguments, dependencies,
                                                     strict_validation)
    auto_provided = _build_auto_provide(arguments, auto_provide, annotated,
                                        strict_validation)
    name_as_dependency = _build_from_arg_names(arguments, use_names, strict_validation)

    resolved_dependencies: List[object] = [
        annotated.get(
            arg.name,
            explicit_dependencies.get(
                arg.name,
                auto_provided.get(
                    arg.name,
                    arg.name if arg.name in name_as_dependency else None)))
        for arg in arguments
    ]

    return InjectionBlueprint(tuple(
        Injection(arg_name=arg.name,
                  required=not arg.has_default,
                  dependency=dependency)
        for arg, dependency in zip(arguments, resolved_dependencies)
    ))


@API.private
def _build_from_annotations(arguments: Arguments) -> Dict[str, Hashable]:
    from ._annotations import extract_annotated_arg_dependency
    arg_to_dependency = {}
    for arg in arguments:
        dependency = extract_annotated_arg_dependency(arg)
        if dependency is not None:
            arg_to_dependency[arg.name] = dependency

    return arg_to_dependency


@API.private
def _build_from_dependencies(arguments: Arguments,
                             dependencies: 'DEPENDENCIES_TYPE',
                             strict_validation: bool
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
        _check_valid_arg_names("dependencies",
                               dependencies.keys(),
                               arguments,
                               strict_validation)
        arg_to_dependency = dependencies
    elif isinstance(dependencies, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        dependencies = tuple(dependencies)
        if strict_validation and len(arguments.without_self) < len(dependencies):
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
def _build_auto_provide(arguments: Arguments,
                        auto_provide: Union[bool, Iterable[Hashable]],
                        annotated: Dict[str, Hashable],
                        strict_validation: bool
                        ) -> Dict[str, Hashable]:
    from ._annotations import extract_auto_provided_arg_dependency

    if auto_provide is True:
        auto_provide = YesSet()
    elif auto_provide is False:
        auto_provide = set()
    elif isinstance(auto_provide, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        auto_provide = set(auto_provide)
        for cls in auto_provide:
            if not (isinstance(cls, type) and inspect.isclass(cls)):
                raise TypeError(f"auto_provide must be a boolean or an iterable of "
                                f"classes, but contains {cls!r} which is not a class.")
    else:
        raise TypeError(f"auto_provide must be a boolean or an iterable of classes,"
                        f"not {type(auto_provide)}.")

    auto_provided = {}
    for arg in arguments.without_self:
        dependency = extract_auto_provided_arg_dependency(arg)
        if dependency is not None and dependency in auto_provide:
            auto_provided[arg.name] = dependency

    provided_dependencies = set(auto_provided.values()).union(annotated.values())
    if strict_validation and not (isinstance(auto_provide, bool)
                                  or auto_provide.issubset(provided_dependencies)):
        raise ValueError(f"Some auto_provide dependencies ({auto_provide}) are not "
                         f"present in the function. Found: {provided_dependencies}\n"
                         f"Either ensure that auto_provide matches the function type "
                         f"hints or consider specifying strict_validation=False")

    return auto_provided


@API.private
def _build_from_arg_names(arguments: Arguments,
                          use_names: Union[bool, Iterable[str]],
                          strict_validation: bool
                          ) -> Set[str]:
    if use_names is False:
        return set()
    elif use_names is True:
        return {arg.name for arg in arguments.without_self}
    elif isinstance(use_names, c_abc.Iterable):
        # convert to Tuple in case we cannot iterate more than once.
        use_names = tuple(use_names)
        _check_valid_arg_names("use_names", use_names, arguments, strict_validation)
        return set(use_names)
    else:
        raise TypeError(f'Only an iterable or a boolean is supported for '
                        f'use_names, not {type(use_names)!r}')


@API.private
def _check_valid_arg_names(param: str,
                           names: Iterable[str],
                           arguments: Arguments,
                           strict_validation: bool) -> None:
    for name in names:
        if not isinstance(name, str):
            raise TypeError(f"{param} expected an argument name (str), "
                            f"not {name!r} ({type(name)})")
        if arguments.has_self and name == arguments[0].name:
            raise ValueError(f"Cannot inject first argument in {param} "
                             f"({arguments[0]!r}) of a method / @classmethod.")

        if strict_validation and name not in arguments:
            raise ValueError(f"Unknown argument in {param}: {name!r}")
