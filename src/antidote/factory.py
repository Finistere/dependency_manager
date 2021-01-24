import inspect
from typing import (Callable, Iterable, Optional, Tuple, TypeVar, Union, cast, overload)

from ._compatibility.typing import Protocol, final, get_type_hints
from ._factory import FactoryMeta, FactoryWrapper, PreBuild
from ._internal import API
from ._internal.utils import Copy, FinalImmutable
from ._internal.wrapper import is_wrapper
from ._providers import FactoryProvider, Tag, TagProvider
from .core import Provide, Scope, Wiring, WithWiringMixin, inject
from .core.exceptions import DoubleInjectionError
from .utils import validated_scope, validated_tags

F = TypeVar('F', bound=Callable[..., object])


@API.private
class FactoryProtocol(Protocol[F]):
    """
    :meta private:
    """

    def __rmatmul__(self, klass: type) -> object:
        pass  # pragma: no cover

    __call__: F


@API.public
class Factory(metaclass=FactoryMeta, abstract=True):
    """
    Abstract base class for a factory which provides a single dependency. The provided
    dependency is defined through the type annotation of :py:meth:`.__call__` which will
    be used to create the dependency.

    The factory instance will only be instantiated once, whether the dependency is a
    singleton, the default, or not. Both :py:meth:`.__init__` and :py:meth:`.__call__`
    are wired by default.

    To retrieve the dependency from Antidote you need to use a specific syntax
    :code:`dependency @ factory` as presented in the following examples. The goal of it is
    twofold:

    - Ensure that the factory is loaded whenever you require the dependency.
    - Better maintainability as you know *where* the dependency comes from.

    .. note::

        If you only need a simple function, consider using :py:func:`.factory` instead.

    .. doctest:: helpers_Factory

        >>> from antidote import Factory, world
        >>> class ExternalService:
        ...     pass
        >>> class MyFactory(Factory):
        ...     def __call__(self) -> ExternalService:
        ...         return ExternalService()
        >>> world.get[ExternalService @ MyFactory]()
        <ExternalService ...>

    For customization use :py:attr:`.__antidote__`:

    .. doctest:: helpers_Factory_v2

        >>> from antidote import Factory, world
        >>> class ExternalService:
        ...     pass
        >>> class MyFactory(Factory):
        ...     __antidote__ = Factory.Conf(singleton=False) \\
        ...         .with_wiring(use_names=True)
        ...
        ...     def __call__(self) -> ExternalService:
        ...         return ExternalService()

    One can customize the instantiation and use the same service with different
    configuration:

    .. doctest:: helpers_Factory_v3

        >>> from antidote import Factory, world, inject
        >>> class ExternalService:
        ...     def __init__(self, name):
        ...         self.name = name
        >>> class MyFactory(Factory):
        ...     def __call__(self, name = 'default') -> ExternalService:
        ...         return ExternalService(name)
        ...
        ...     @classmethod
        ...     def named(cls, name: str):
        ...         return cls._with_kwargs(name=name)
        ...
        >>> world.get[ExternalService](ExternalService @ MyFactory).name
        'default'
        >>> s = world.get[ExternalService](
        ...     ExternalService @ MyFactory.named('perfection'))
        >>> s.name
        'perfection'
        >>> # The same instance will be returned for those keywords as MyFactory was
        ... # declared as returning a singleton.
        ... s is world.get(ExternalService @ MyFactory.named('perfection'))
        True
        >>> # You can also keep the dependency and re-use it
        ... PerfectionService = ExternalService @ MyFactory.named('perfection')
        >>> @inject(dependencies=dict(service=PerfectionService))
        ... def f(service):
        ...     return service
        >>> f() is s
        True

    """

    @final
    class Conf(FinalImmutable, WithWiringMixin):
        """
        Immutable factory configuration. To change parameters on a existing instance, use
        either method :py:meth:`.copy` or
        :py:meth:`.core.wiring.WithWiringMixin.with_wiring`.
        """
        __slots__ = ('wiring', 'scope', 'tags')
        wiring: Optional[Wiring]
        scope: Optional[Scope]
        tags: Optional[Tuple[Tag]]

        @property
        def singleton(self) -> bool:
            return self.scope is Scope.singleton()

        def __init__(self,
                     *,
                     wiring: Optional[Wiring] = Wiring(),
                     singleton: bool = None,
                     scope: Optional[Scope] = Scope.sentinel(),
                     tags: Iterable[Tag] = None):
            """

            Args:
                wiring: Wiring to be applied on the factory. By default only
                    :code:`__init__()` and :code:`__call__()` will be wired. To deactivate
                    any wiring at all use :py:obj:`None`.
                singleton: Whether the returned dependency  is a singleton or not. If yes,
                    the factory will be called at most once and the result re-used.
                    Mutually exclusive with :code:`scope`. Defaults to :py:obj:`True`
                scope: Scope of the returned dependency. Mutually exclusive with
                    :code:`singleton`. The scope defines if and how long the returned
                    dependency will be cached. See :py:class:`~.core.container.Scope`.
                    Defaults to :py:meth:`~.core.container.Scope.singleton`.
                tags: Iterable of :py:class:`~.._providers.tag.Tag` tagging to the
                      provided dependency.
            """
            if not (wiring is None or isinstance(wiring, Wiring)):
                raise TypeError(f"wiring must be a Wiring or None, "
                                f"not {type(wiring)}")

            super().__init__(wiring=wiring,
                             scope=validated_scope(scope,
                                                   singleton,
                                                   default=Scope.singleton()),
                             tags=validated_tags(tags))

        def copy(self,
                 *,
                 wiring: Union[Optional[Wiring], Copy] = Copy.IDENTICAL,
                 singleton: Union[bool, Copy] = Copy.IDENTICAL,
                 scope: Union[Optional[Scope], Copy] = Copy.IDENTICAL,
                 tags: Union[Optional[Iterable[Tag]], Copy] = Copy.IDENTICAL
                 ) -> 'Factory.Conf':
            """
            Copies current configuration and overrides only specified arguments.
            Accepts the same arguments as :py:meth:`.__init__`
            """
            if not (singleton is Copy.IDENTICAL or scope is Copy.IDENTICAL):
                raise TypeError("Use either singleton or scope argument, not both.")
            if isinstance(singleton, bool):
                scope = Scope.singleton() if singleton else None
            return Copy.immutable(self,
                                  wiring=wiring,
                                  scope=scope,
                                  tags=tags)

    __antidote__: Conf = Conf()
    """
    Configuration of the factory. Defaults to wire :py:meth:`.__init__` and
    :py:meth:`.__call__`.
    """

    def __call__(self) -> object:
        raise NotImplementedError()  # pragma: no cover


@overload
def factory(f: F,  # noqa: E704  # pragma: no cover
            *,
            singleton: bool = None,
            scope: Optional[Scope] = Scope.sentinel(),
            tags: Iterable[Tag] = None
            ) -> FactoryProtocol[F]: ...


@overload
def factory(*,  # noqa: E704  # pragma: no cover
            singleton: bool = None,
            scope: Optional[Scope] = Scope.sentinel(),
            tags: Iterable[Tag] = None
            ) -> Callable[[F], FactoryProtocol[F]]: ...


@API.public
def factory(f: F = None,
            *,
            singleton: bool = None,
            scope: Optional[Scope] = Scope.sentinel(),
            tags: Iterable[Tag] = None
            ) -> Union[FactoryProtocol[F], Callable[[F], FactoryProtocol[F]]]:
    """
    Registers a factory which provides as single dependency, defined through the return
    type annotation.

    To retrieve the dependency from Antidote you need to use a specific syntax
    :code:`dependency @ factory` as presented in the following examples. The goal of it is
    twofold:

    - Ensure that the factory is loaded whenever you require the dependency.
    - Better maintainability as you know *where* the dependency comes from.

    .. note::

        If you need a stateful factory or want to implement a complex one prefer using
        :py:class:`.Factory` instead.

    .. doctest:: helpers_factory

        >>> from antidote import factory, world
        >>> class ExternalService:
        ...     pass
        >>> @factory
        ... def build_service() -> ExternalService:
        ...     return ExternalService()
        >>> world.get[ExternalService](ExternalService @ build_service)
        <ExternalService ...>

    Args:
        f: Callable which builds the dependency.
        singleton: Whether the returned dependency  is a singleton or not. If yes,
            the factory will be called at most once and the result re-used. Mutually
            exclusive with :code:`scope`. Defaults to :py:obj:`True`.
        scope: Scope of the returned dependency. Mutually exclusive with
            :code:`singleton`. The scope defines if and how long the returned dependency
            will be cached. See :py:class:`~.core.container.Scope`. Defaults to
            :py:meth:`~.core.container.Scope.singleton`.
        tags: Iterable of :py:class:`~.._providers.tag.Tag` applied to the provided
            dependency.

    Returns:
        The factory or the function decorator.

    """
    scope = validated_scope(scope, singleton, default=Scope.singleton())
    tags = validated_tags(tags)

    @inject
    def register_factory(func: F,
                         factory_provider: Provide[FactoryProvider] = None,
                         tag_provider: Provide[TagProvider] = None) -> FactoryProtocol[F]:
        assert factory_provider is not None

        if not (inspect.isfunction(func)
                or (is_wrapper(func)
                    and inspect.isfunction(func.__wrapped__))):  # type: ignore
            raise TypeError(f"{func} is not a function")

        output = get_type_hints(func).get('return')
        if output is None:
            raise ValueError("A return type hint is necessary. "
                             "It is used a the dependency.")
        if not inspect.isclass(output):
            raise TypeError(f"The return type hint is expected to be a class, "
                            f"not {type(output)}.")

        if tags is not None and tag_provider is None:
            raise RuntimeError("No TagProvider registered, cannot use tags.")

        try:
            func = inject(func)
        except DoubleInjectionError:
            pass

        dependency = factory_provider.register(factory=func,
                                               scope=scope,
                                               output=output)

        if tags:
            assert tag_provider is not None  # for Mypy
            tag_provider.register(dependency=dependency, tags=tags)

        return cast(FactoryProtocol[F], FactoryWrapper(func, dependency))

    return f and register_factory(f) or register_factory
