import collections.abc as c_abc
import enum
from typing import (Callable, FrozenSet, Hashable, Iterable, Optional, TypeVar,
                    Union,
                    overload)

from .injection import DEPENDENCIES_TYPE, validate_injection
from .._compatibility.typing import final
from .._internal import API
from .._internal.utils import Copy, FinalImmutable

C = TypeVar('C', bound=type)
_empty_set: FrozenSet[str] = frozenset()


class Methods(enum.Enum):
    ALL = enum.auto()


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

    Injection arguments (:code:`dependencies`, :code:`use_names`,  :code:`auto_provide`)
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
    __slots__ = ('methods', 'auto_provide', 'dependencies', 'use_names',
                 'raise_on_double_injection')
    methods: Union[Methods, FrozenSet[str]]
    """Method names that must be injected."""
    dependencies: DEPENDENCIES_TYPE
    use_names: Union[bool, FrozenSet[str]]
    auto_provide: Union[bool, FrozenSet[str]]
    raise_on_double_injection: bool

    def __init__(self,
                 *,
                 methods: Union[Methods, Iterable[str]] = Methods.ALL,
                 dependencies: DEPENDENCIES_TYPE = None,
                 use_names: Union[bool, Iterable[str]] = False,
                 auto_provide: Union[bool, Iterable[Hashable]] = False,
                 raise_on_double_injection: bool = False) -> None:
        """
        Args:
            methods: Names of methods to be injected. If any of them is already injected,
                an error will be raised. Consider using :code:`attempt_methods` otherwise.
            dependencies: Propagated for every method to :py:func:`~.injection.inject`
            use_names: Propagated for every method to :py:func:`~.injection.inject`
            auto_provide: Propagated for every method to :py:func:`~.injection.inject`
        """
        if not isinstance(raise_on_double_injection, bool):
            raise TypeError(f"raise_on_double_injection must be a boolean, "
                            f"not {type(raise_on_double_injection)}")

        if isinstance(auto_provide, str) \
                or not isinstance(auto_provide, (c_abc.Iterable, bool)):
            raise TypeError(f"auto_provide must be an iterable of method names, "
                            f"not {type(auto_provide)}.")
        if isinstance(auto_provide, c_abc.Iterable):
            auto_provide = frozenset(auto_provide)

        if isinstance(methods, str) or not isinstance(methods, (c_abc.Iterable, Methods)):
            raise TypeError(f"methods must be an iterable of method names, "
                            f"not {type(methods)}.")
        elif isinstance(methods, c_abc.Iterable):
            methods = frozenset(methods)
            if not all(isinstance(method, str) for method in methods):
                raise TypeError("methods is expected to contain methods names (str)")

        if not isinstance(use_names, str) and isinstance(use_names, c_abc.Iterable):
            use_names = frozenset(use_names)
        if not isinstance(auto_provide, str) and isinstance(auto_provide,
                                                            c_abc.Iterable):
            auto_provide = frozenset(auto_provide)
        validate_injection(dependencies, use_names, auto_provide)

        super().__init__(methods=methods,
                         dependencies=dependencies,
                         use_names=use_names,
                         auto_provide=auto_provide,
                         raise_on_double_injection=raise_on_double_injection)

    def copy(self,
             *,
             methods: Union[Methods, Iterable[str], Copy] = Copy.IDENTICAL,
             dependencies: Union[Optional[DEPENDENCIES_TYPE], Copy] = Copy.IDENTICAL,
             use_names: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
             auto_provide: Union[bool, Iterable[Hashable], Copy] = Copy.IDENTICAL,
             raise_on_double_injection: Union[bool, Copy] = Copy.IDENTICAL
             ) -> 'Wiring':
        """
        Copies current wiring and overrides only specified arguments.
        Accepts the same arguments as :py:meth:`.__init__`
        """
        return Copy.immutable(self,
                              methods=methods,
                              dependencies=dependencies,
                              use_names=use_names,
                              auto_provide=auto_provide,
                              raise_on_double_injection=raise_on_double_injection)

    def wire(self, __klass: C) -> C:
        """
        Used to wire a class with specified configuration.

        Args:
            __klass: Class to wired

        Returns:
            The same class object with specified methods injected.
        """
        from ._wiring import wire_class
        return wire_class(__klass, self)


@overload
def wire(__klass: C,  # noqa: E704  # pragma: no cover
         *,
         methods: Union[Methods, Iterable[str]] = Methods.ALL,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         auto_provide: Union[bool, Iterable[Hashable]] = False,
         raise_on_double_injection: bool = False
         ) -> C: ...


@overload
def wire(*,  # noqa: E704  # pragma: no cover
         methods: Union[Methods, Iterable[str]] = Methods.ALL,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         auto_provide: Union[bool, Iterable[Hashable]] = False,
         raise_on_double_injection: bool = False
         ) -> Callable[[C], C]: ...


@API.public
def wire(__klass: C = None,
         *,
         methods: Union[Methods, Iterable[str]] = Methods.ALL,
         dependencies: DEPENDENCIES_TYPE = None,
         use_names: Union[bool, Iterable[str]] = False,
         auto_provide: Union[bool, Iterable[Hashable]] = False,
         raise_on_double_injection: bool = False
         ) -> Union[C, Callable[[C], C]]:
    """
    Wire a class by injecting specified methods. This avoids repetition if similar
    dependencies need to be injected in different methods.

    Injection arguments (:code:`dependencies`, :code:`use_names`,  :code:`auto_provide`)
    are adapted for match the arguments of the method. Hence :py:func:`~.injection.inject`
    won't raise an error that it has too much dependencies.

    Args:
        __klass: Class to wire.
        methods: Names of methods that must be injected.
        dependencies: Propagated for every method to :py:func:`~.injection.inject`.
        use_names: Propagated for every method to :py:func:`~.injection.inject`.
        auto_provide: Propagated for every method to :py:func:`~.injection.inject`.

    Returns:
        Wired class or a class decorator.

    """
    wiring = Wiring(
        methods=methods,
        dependencies=dependencies,
        use_names=use_names,
        auto_provide=auto_provide,
        raise_on_double_injection=raise_on_double_injection
    )

    def wire_methods(cls: C) -> C:
        from ._wiring import wire_class
        return wire_class(cls, wiring)

    return __klass and wire_methods(__klass) or wire_methods


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

    def auto_provide(self: W) -> W:
        return self.copy(wiring=(Wiring(auto_provide=True)
                                 if self.wiring is None else
                                 self.wiring.copy(auto_provide=True)))

    def with_wiring(self: W,
                    *,
                    methods: Union[Methods, Iterable[str], Copy] = Copy.IDENTICAL,
                    dependencies: Union[DEPENDENCIES_TYPE, Copy] = Copy.IDENTICAL,
                    use_names: Union[bool, Iterable[str], Copy] = Copy.IDENTICAL,
                    auto_provide: Union[bool, Iterable[Hashable], Copy] = Copy.IDENTICAL,
                    raise_on_double_injection: Union[bool, Copy] = Copy.IDENTICAL,
                    ) -> W:
        """
        Accepts the same arguments as :py:class:`~.Wiring`. And behaves the same way
        as :py:meth:`.Wiring.copy`.

        Returns:
            Copy of current instance with its :code:`wiring` attribute modified with
            provided arguments.
        """
        if self.wiring is None:
            return self.copy(wiring=Wiring().copy(
                methods=methods,
                dependencies=dependencies,
                use_names=use_names,
                auto_provide=auto_provide,
                raise_on_double_injection=raise_on_double_injection))
        else:
            return self.copy(wiring=self.wiring.copy(
                methods=methods,
                dependencies=dependencies,
                use_names=use_names,
                auto_provide=auto_provide,
                raise_on_double_injection=raise_on_double_injection))
