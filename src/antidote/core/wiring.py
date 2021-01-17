import collections.abc as c_abc
from typing import (Callable, FrozenSet, Iterable, Optional, Tuple, TypeVar, Union,
                    overload)

from .injection import DEPENDENCIES_TYPE, validate_injection
from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import Copy, FinalImmutable

C = TypeVar('C', bound=type)
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
    __slots__ = ('methods', 'auto_wire', 'dependencies', 'use_names',
                 'use_type_hints')
    auto_wire: Union[bool, FrozenSet[str]]
    methods: FrozenSet[str]
    """Method names that must be injected."""
    dependencies: DEPENDENCIES_TYPE
    use_names: Union[bool, FrozenSet[str]]
    use_type_hints: Union[bool, FrozenSet[str]]

    def __init__(self,
                 *,
                 auto_wire: Union[bool, Iterable[str]] = False,
                 methods: Iterable[str] = None,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = False,
                 use_type_hints: Union[bool, Iterable[str]] = False) -> None:
        """
        Args:
            methods: Names of methods to be injected. If any of them is already injected,
                an error will be raised. Consider using :code:`attempt_methods` otherwise.
            attempt_methods: Names of methods that will be injected if present and if not
                already injected. Typically used to declare methods that should be
                injected in subclasses.
            dependencies: Propagated for every method to :py:func:`~.injection.inject`
            use_names: Propagated for every method to :py:func:`~.injection.inject`
            use_type_hints: Propagated for every method to :py:func:`~.injection.inject`
        """

        if isinstance(auto_wire, str) \
                or not isinstance(auto_wire, (c_abc.Iterable, bool)):
            raise TypeError(f"auto_wire must be an iterable of method names, "
                            f"not {type(auto_wire)}.")
        if isinstance(auto_wire, c_abc.Iterable):
            auto_wire = frozenset(auto_wire)
            if not all(isinstance(method, str) for method in auto_wire):
                raise TypeError("auto_wire is expected to contain methods names (str)")

        if methods is None:
            methods = frozenset()
        elif isinstance(methods, str) or not isinstance(methods, c_abc.Iterable):
            raise TypeError(f"methods must be an iterable of method names, "
                            f"not {type(methods)}.")
        else:
            methods = frozenset(methods)
        if not all(isinstance(method, str) for method in methods):
            raise TypeError("methods is expected to contain methods names (str)")

        if not isinstance(use_names, str) and isinstance(use_names, c_abc.Iterable):
            use_names = frozenset(use_names)
        if not isinstance(use_type_hints, str) and isinstance(use_type_hints,
                                                              c_abc.Iterable):
            use_type_hints = frozenset(use_type_hints)
        validate_injection(dependencies, use_names, use_type_hints)

        super().__init__(auto_wire=auto_wire,
                         methods=methods,
                         dependencies=dependencies,
                         use_names=use_names,
                         use_type_hints=use_type_hints)

    def copy(self,
             *,
             auto_wire: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
             methods: Union[Iterable[str], Copy] = Copy.IDENTICAL,
             dependencies: Union[Optional[DEPENDENCIES_TYPE], Copy] = Copy.IDENTICAL,
             use_names: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
             use_type_hints: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL
             ) -> 'Wiring':
        """
        Copies current wiring and overrides only specified arguments.
        Accepts the same arguments as :py:meth:`.__init__`
        """
        return Copy.immutable(self,
                              methods=methods,
                              auto_wire=auto_wire,
                              dependencies=dependencies,
                              use_names=use_names,
                              use_type_hints=use_type_hints)

    def wire(self, klass: C) -> C:
        """
        Used to wire a class with specified configuration.

        Args:
            klass: Class to wired

        Returns:
            The same class object with specified methods injected.
        """
        from ._wiring import wire_class
        return wire_class(klass, self)


@overload
def wire(klass: C,  # noqa: E704  # pragma: no cover
         *,
         auto_wire: Union[bool, Iterable[str]] = False,
         methods: Iterable[str] = None,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         use_type_hints: Union[bool, Iterable[str]] = False
         ) -> C: ...


@overload
def wire(*,  # noqa: E704  # pragma: no cover
         auto_wire: Union[bool, Iterable[str]] = False,
         methods: Iterable[str] = None,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         use_type_hints: Union[bool, Iterable[str]] = False
         ) -> Callable[[C], C]: ...


@API.public
def wire(klass: C = None,
         *,
         auto_wire: Union[bool, Iterable[str]] = False,
         methods: Iterable[str] = None,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         use_type_hints: Union[bool, Iterable[str]] = False
         ) -> Union[C, Callable[[C], C]]:
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

    Returns:
        Wired class or a class decorator.

    """
    wiring = Wiring(
        auto_wire=auto_wire,
        methods=methods,
        dependencies=dependencies,
        use_names=use_names,
        use_type_hints=use_type_hints
    )

    def wire_methods(cls: C) -> C:
        from ._wiring import wire_class
        return wire_class(cls, wiring)

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

    def auto_wire(self: W, *methods: str) -> W:
        if not methods:
            auto_wire: Union[bool, Tuple[str, ...]] = True
        else:
            if not all(isinstance(method, str) for method in methods):
                raise TypeError("auto_wire can only be called with methods names (str)")
            auto_wire = methods

        return self.copy(wiring=(Wiring(auto_wire=auto_wire)
                                 if self.wiring is None else
                                 self.wiring.copy(auto_wire=auto_wire)))

    def with_wiring(self: W,
                    *,
                    methods: Iterable[str],
                    dependencies: DEPENDENCIES_TYPE = None,
                    use_names: Union[bool, Iterable[str]] = False,
                    use_type_hints: Union[bool, Iterable[str]] = False
                    ) -> W:
        """
        Accepts the same arguments as :py:class:`~.Wiring`. And behaves the same way
        as :py:meth:`.Wiring.copy`.

        Returns:
            Copy of current instance with its :code:`wiring` attribute modified with
            provided arguments.
        """
        if self.wiring is None:
            return self.copy(wiring=Wiring(methods=methods,
                                           dependencies=dependencies,
                                           use_names=use_names,
                                           use_type_hints=use_type_hints))
        else:
            return self.copy(wiring=self.wiring.copy(methods=methods,
                                                     dependencies=dependencies,
                                                     use_names=use_names,
                                                     use_type_hints=use_type_hints))
