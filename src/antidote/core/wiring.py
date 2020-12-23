import collections.abc as c_abc
import enum
import inspect
from typing import Callable, cast, FrozenSet, Iterable, Optional, overload, TypeVar, Union

from ._injection import raw_inject
from .exceptions import DoubleInjectionError
from .injection import DEPENDENCIES_TYPE, validate_injection
from .._compatibility.typing import final
from .._internal import API
from .._internal.argspec import Arguments
from .._internal.utils import Copy, FinalImmutable, raw_getattr

C = TypeVar('C', bound=type)
AnyF = Union[Callable[..., object], staticmethod, classmethod]
_empty_set: FrozenSet[str] = frozenset()


@API.public
@final
class Wiring(FinalImmutable):
    """
    Defines how a class should be wired, meaning if/how/which methods are injected. This
    class is intended to be used by configuration objects. If you just want to wire a
    single class, consider using the class decorator :py:func:`~.wire` instead. There are
    two purposes:

    - providing a default injection which can be overridden either by changing the wiring
      or using `@inject` when using :code:`attempt_methods`.
    - wiring of multiple methods with similar dependencies.

    Injection arguments (:code:`dependencies`, :code:`use_names`,  :code:`use_type_hints`)
    are adapted for match the arguments of the method. Hence :py:func:`~.injection.inject`
    won't raise an error that it has too much dependencies.

    Instances are immutable. If you want to change some parameters, typically defaults
    defined by Antidote, you'll need to rely on :py:meth:`~.copy`. It accepts the same
    arguments as :py:meth:`~.__init__` and overrides existing values.

    .. doctest:: core_Wiring

        >>> from antidote import Wiring
        >>> # Methods must always be specified.
        ... w = Wiring(methods=['my_method', 'other_method'])
        >>> # Now argument names will be used on both my_method and other_method.
        ... w_copy = w.copy(use_names=True)

    """
    __slots__ = ('methods', 'attempt_methods', 'dependencies', 'use_names',
                 'use_type_hints', 'wire_super')
    methods: FrozenSet[str]
    attempt_methods: FrozenSet[str]
    """Method names that must be injected."""
    wire_super: Union[bool, FrozenSet[str]]
    """Method names for which an exception will not be raised if not found."""
    dependencies: DEPENDENCIES_TYPE
    use_names: Union[bool, FrozenSet[str]]
    use_type_hints: Union[bool, FrozenSet[str]]

    def __init__(self,
                 *,
                 methods: Iterable[str] = None,
                 attempt_methods: Iterable[str] = None,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = None,
                 use_type_hints: Union[bool, Iterable[str]] = None,
                 wire_super: Union[bool, Iterable[str]] = None) -> None:
        """
        Args:
            methods: Names of methods that must be injected.
            attempt_methods: Names of methods that will be injected if present and if not
                already injected.
            dependencies: Propagated for every method to :py:func:`~.injection.inject`
            use_names: Propagated for every method to :py:func:`~.injection.inject`
            use_type_hints: Propagated for every method to :py:func:`~.injection.inject`
            wire_super: Method names which may be retrieved in a parent class. By default,
                only methods  directly defined in the class itself may be injected. If
                :py:obj:`True` all methods will be searched in parent classes. Defaults to
                :py:obj:`False`.
        """
        if attempt_methods is None and methods is None:
            raise TypeError("Either methods or attempt_methods must be specified.")

        if attempt_methods is None:
            attempt_methods = frozenset()
        elif not isinstance(attempt_methods, c_abc.Iterable) \
                or isinstance(attempt_methods, str):
            raise TypeError(f"attempt_methods must be an iterable of method names, "
                            f"not {type(attempt_methods)}.")
        else:
            attempt_methods = frozenset(attempt_methods)
        if not all(isinstance(method, str) for method in attempt_methods):
            raise ValueError("attempt_methods is expected to contain methods names (str)")

        if methods is None:
            methods = frozenset()
        elif not isinstance(methods, c_abc.Iterable) or isinstance(methods, str):
            raise TypeError(f"methods must be an iterable of method names, "
                            f"not {type(methods)}.")
        else:
            methods = frozenset(methods)
        if not all(isinstance(method, str) for method in methods):
            raise ValueError("methods is expected to contain methods names (str)")

        if not methods and not attempt_methods:
            raise ValueError("Either methods or attempt_methods must contain at least "
                             "one method name.")
        attempt_methods -= methods

        if not isinstance(use_names, str) and isinstance(use_names, c_abc.Iterable):
            use_names = frozenset(use_names)
        if not isinstance(use_type_hints, str) and isinstance(use_type_hints,
                                                              c_abc.Iterable):
            use_type_hints = frozenset(use_type_hints)
        validate_injection(dependencies, use_names, use_type_hints)

        if not (wire_super is None or isinstance(wire_super, (bool, c_abc.Iterable))) \
                or isinstance(wire_super, str):
            raise TypeError(f"wire_super must be either a boolean or a whitelist of "
                            f"methods names, not {type(wire_super)!r}.")
        if wire_super is None or isinstance(wire_super, bool):
            wire_super = bool(wire_super)
        else:
            wire_super = frozenset(wire_super)
            if not wire_super.issubset(methods | attempt_methods):
                all_methods = methods | attempt_methods
                raise ValueError(f"wire_super is not a subset of methods. Method "
                                 f"names {wire_super - all_methods!r} are unknown.")

        super().__init__(methods=methods,
                         attempt_methods=attempt_methods,
                         wire_super=wire_super,
                         dependencies=dependencies,
                         use_names=use_names,
                         use_type_hints=use_type_hints)

    def copy(self,
             *,
             methods: Union[Iterable[str], Copy] = Copy.IDENTICAL,
             attempt_methods: Union[Iterable[str], Copy] = Copy.IDENTICAL,
             dependencies: Union[DEPENDENCIES_TYPE, Copy] = Copy.IDENTICAL,
             use_names: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
             use_type_hints: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
             wire_super: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL
             ) -> 'Wiring':
        """
        All arguments are passed to :py:meth:`.__init__` if specified. If not the current
        ones are used.

        Returns:
            Wiring: copy of the current object with the specified attributes overriding
            existing ones.
        """
        return Copy.immutable(self,
                              methods=methods,
                              attempt_methods=attempt_methods,
                              wire_super=wire_super,
                              dependencies=dependencies,
                              use_names=use_names,
                              use_type_hints=use_type_hints)

    @API.experimental
    def wire(self, klass: C) -> C:
        """**Experimental**

        Used to wire a class with specified configuration.

        Args:
            klass: Class to wired

        Returns:
            The same class object with specified methods injected.
        """
        return _wire_class(klass, self)


@overload
def wire(klass: C,  # noqa: E704  # pragma: no cover
         *,
         methods: Iterable[str],
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = None,
         use_type_hints: Union[bool, Iterable[str]] = None,
         wire_super: Union[bool, Iterable[str]] = None
         ) -> C: ...


@overload
def wire(*,  # noqa: E704  # pragma: no cover
         methods: Iterable[str],
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = None,
         use_type_hints: Union[bool, Iterable[str]] = None,
         wire_super: Union[bool, Iterable[str]] = None
         ) -> Callable[[C], C]: ...


@API.public
def wire(klass: C = None,
         *,
         methods: Iterable[str],
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = None,
         use_type_hints: Union[bool, Iterable[str]] = None,
         wire_super: Union[bool, Iterable[str]] = None) -> Union[C, Callable[[C], C]]:
    """
    Wire a class by injecting specified methods. This avoids repetition if similar
    dependencies need to be injected in different methods.

    Injection arguments (:code:`dependencies`, :code:`use_names`,  :code:`use_type_hints`)
    are adapted for match the arguments of the method. Hence :py:func:`~.injection.inject`
    won't raise an error that it has too much dependencies.

    Args:
        klass: Class to wire.
        methods: Names of methods that must be injected.
        dependencies: Propagated for every method to :py:func:`~.injection.inject`.
        use_names: Propagated for every method to :py:func:`~.injection.inject`.
        use_type_hints: Propagated for every method to :py:func:`~.injection.inject`.
        wire_super: Method names which may be retrieved in a parent class. By default,
            only methods directly defined in the class itself may be injected. If set to
            :py:obj:`True`, it will applied to all methods..

    Returns:
        Wired class or a class decorator.

    """
    wiring = Wiring(
        methods=methods,
        wire_super=wire_super,
        dependencies=dependencies,
        use_names=use_names,
        use_type_hints=use_type_hints
    )

    def wire_methods(cls: C) -> C:
        return _wire_class(cls, wiring)

    return klass and wire_methods(klass) or wire_methods


W = TypeVar('W', bound='WithWiringMixin')


@API.experimental
class WithWiringMixin:
    """**Experimental**

    Used by configuration classes (immutable having a :code:`copy()` method) with a
    :code:`wiring` attribute to change it more simply with the :py:meth:`~.with_wiring`
    method.
    """
    __slots__ = ()

    wiring: Optional[Wiring]

    def copy(self: W, *, wiring: Union[Optional[Wiring], Copy] = Copy.IDENTICAL) -> W:
        raise NotImplementedError()  # pragma: no cover

    def with_wiring(self: W,
                    *,
                    methods: Union[Iterable[str], Copy] = Copy.IDENTICAL,
                    attempt_methods: Union[Iterable[str], Copy] = Copy.IDENTICAL,
                    dependencies: Union[DEPENDENCIES_TYPE, Copy] = Copy.IDENTICAL,
                    use_names: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
                    use_type_hints: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
                    wire_super: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL
                    ) -> W:
        """
        Accepts the same arguments as :py:class:`~.Wiring`. And behaves the same way
        as :py:meth:`.Wiring.copy`.

        Returns:
            Copy of current instance with its :code:`wiring` attribute modified with
            provided arguments.
        """
        if self.wiring is None:
            if methods is Copy.IDENTICAL and attempt_methods is Copy.IDENTICAL:
                raise TypeError("Current wiring is None, so either methods or"
                                "attempt_methods must be specified")
            wiring = Wiring(
                methods=[] if methods is Copy.IDENTICAL else methods,
                attempt_methods=([]
                                 if attempt_methods is Copy.IDENTICAL else
                                 attempt_methods))
            return self.copy(wiring=wiring.copy(
                dependencies=dependencies,
                use_names=use_names,
                use_type_hints=use_type_hints,
                wire_super=wire_super))
        else:
            return self.copy(wiring=self.wiring.copy(
                methods=methods,
                attempt_methods=attempt_methods,
                dependencies=dependencies,
                use_names=use_names,
                use_type_hints=use_type_hints,
                wire_super=wire_super))


@API.private  # Used internally for auto wiring.
class AutoWire(enum.Enum):
    auto = object()


@API.private  # Use wire() or Wiring.wire() instead
def _wire_class(cls: C, wiring: Wiring) -> C:
    if not inspect.isclass(cls):
        raise TypeError(f"Expecting a class, got a {type(cls)}")

    if isinstance(wiring.wire_super, bool):
        if wiring.wire_super:
            wire_super_set = wiring.methods | wiring.attempt_methods
        else:
            wire_super_set = frozenset()
    else:
        wire_super_set = wiring.wire_super

    for method_name in (wiring.methods | wiring.attempt_methods):
        try:
            attr = raw_getattr(cls,
                               method_name,
                               with_super=method_name in wire_super_set)
        except AttributeError:
            if method_name in wiring.methods:
                raise
        else:
            if not (callable(attr)
                    or isinstance(attr, (staticmethod, classmethod))):
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

            if use_names is not None and not isinstance(use_names, bool):
                use_names = use_names.intersection(arguments.arg_names)

            if use_type_hints is not None and not isinstance(use_type_hints, bool):
                use_type_hints = use_type_hints.intersection(arguments.arg_names)

            try:
                injected_method = raw_inject(
                    method,
                    arguments=arguments,
                    dependencies=dependencies,
                    use_names=use_names,
                    use_type_hints=use_type_hints
                )
            except DoubleInjectionError:
                if method_name in wiring.methods:
                    raise
            else:
                if injected_method is not method:  # If something has changed
                    setattr(cls, method_name, injected_method)

    return cls
