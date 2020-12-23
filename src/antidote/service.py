import collections.abc as c_abc
from typing import Callable, cast, Iterable, Optional, overload, Tuple, TypeVar, Union

from ._compatibility.typing import final
from ._internal import API
from ._internal.utils import Copy, FinalImmutable
from ._providers import Tag
from ._service import ServiceMeta
from .core.exceptions import DuplicateDependencyError
from .core.wiring import AutoWire, Wiring, WithWiringMixin

C = TypeVar('C', bound=type)


@API.public
class Service(metaclass=ServiceMeta, abstract=True):
    """
    Abstract base class for a service. It can be retrieved from Antidote simply with its
    class. It will only be instantiated when necessary. By default a service will be
    a singleton and :py:meth:`.__init__` will be wired (injected).

    .. doctest:: helpers_Service

        >>> from antidote import Service, world
        >>> class MyService(Service):
        ...     pass
        >>> world.get[MyService]()
        <MyService ...>

    For customization use :py:attr:`.__antidote__`:

    .. doctest:: helpers_Service_v2

        >>> from antidote import Service, world
        >>> class MyService(Service):
        ...     __antidote__ = Service.Conf(singleton=False) \\
        ...         .with_wiring(use_names=True)

    One can customize the instantiation and use the same service with different
    configuration:

    .. doctest:: helpers_Service_v3

        >>> from antidote import Service, world, inject
        >>> class MyService(Service):
        ...     def __init__(self, name = 'default'):
        ...         self.name = name
        >>> world.get[MyService]().name
        'default'
        >>> s = world.get[MyService](MyService.with_kwargs(name='perfection'))
        >>> s.name
        'perfection'
        >>> # The same instance will be returned for those keywords as MyService is
        ... # defined as a singleton.
        ... s is world.get(MyService.with_kwargs(name='perfection'))
        True
        >>> # You can also keep the dependency and re-use it
        ... PerfectionService = MyService.with_kwargs(name='perfection')
        >>> @inject(dependencies=dict(service=PerfectionService))
        ... def f(service):
        ...     return service
        >>> f() is s
        True

    """

    @final
    class Conf(FinalImmutable, WithWiringMixin):
        """
        Immutable service configuration. To change parameters on a existing instance, use
        either method :py:meth:`.copy` or
        :py:meth:`.core.wiring.WithWiringMixin.with_wiring`.
        """
        __slots__ = ('wiring', 'singleton', 'tags', 'factory')
        wiring: Optional[Wiring]
        singleton: bool
        tags: Optional[Tuple[Tag]]

        def __init__(self,
                     *,
                     wiring: Optional[Union[Wiring, AutoWire]] =
                     Wiring(attempt_methods=['__init__']),
                     singleton: bool = True,
                     tags: Optional[Iterable[Tag]] = None):
            """
            Args:
                wiring: Wiring to be applied on the service. By default only
                    :code:`__init__()` will be wired. Unless :py:attr:`.factory` is class
                    method name, in which case only the latter would be wired. To
                    deactivate any wiring at all use :py:obj:`None`.
                singleton: Whether the service is a singleton or not. A singleton is
                    instantiated only once. Defaults to :py:obj:`True`
                tags: Iterable of :py:class:`~.._providers.tag.Tag` tagging to the
                      service.
            """
            if not isinstance(singleton, bool):
                raise TypeError(f"singleton can be a boolean, "
                                f"but not a {type(singleton)}")
            if not (tags is None or isinstance(tags, c_abc.Iterable)):
                raise TypeError(f"tags can be None or an iterable of strings/Tags, "
                                f"but not a {type(tags)}")
            elif tags is not None:
                tags = tuple(tags)
                if not all(isinstance(t, Tag) for t in tags):
                    raise TypeError(f"Not all tags were instances of Tag: {tags}")
            if not (wiring is None or isinstance(wiring, Wiring)):
                raise TypeError(f"wiring can be None or a Wiring, "
                                f"but not a {type(wiring)}")
            super().__init__(wiring=wiring, singleton=singleton, tags=tags)

        def copy(self,
                 *,
                 wiring: Union[Optional[Wiring], Copy] = Copy.IDENTICAL,
                 singleton: Union[bool, Copy] = Copy.IDENTICAL,
                 tags: Union[Optional[Iterable[Tag]], Copy] = Copy.IDENTICAL
                 ) -> 'Service.Conf':
            """
            Copies current configuration and overrides only specified arguments.
            Accepts the same arguments as :py:meth:`.__init__`
            """
            return Copy.immutable(self, wiring=wiring, singleton=singleton, tags=tags)

    __antidote__: Conf = Conf()
    """
    Configuration of the service. Defaults to wire :py:meth:`.__init__`.
    """


@overload
def service(klass: C,  # noqa: E704  # pragma: no cover
            *,
            singleton: bool = True,
            tags: Iterable[Tag] = None
            ) -> C: ...


@overload
def service(*,  # noqa: E704  # pragma: no cover
            singleton: bool = True,
            tags: Iterable[Tag] = None
            ) -> Callable[[C], C]: ...


@API.experimental
def service(klass: C = None,
            *,
            singleton: bool = True,
            tags: Iterable[Tag] = None) -> Union[C, Callable[[C], C]]:
    """
    Register a service: the class itself is the dependency. Prefer using
    :py:class:`.Service` when possible, it provides more features such as
    :py:meth:`.Service.with_kwargs` and wiring. This decorator is intended for
    registration of class which cannot inherit :py:class:`.Service`. No changes will
    on the class.

    .. doctest:: helpers_register

        >>> from antidote import service
        >>> @service
        ... class CannotInheritService:
        ...     pass

    .. note::

        If your wish to declare to register an external class to Antidote, prefer using
        a factory with either :py:class:`~.extension.factory.Factory` or
        :py:func:`~.extension.factory.factory`.

    Args:
        klass: Class to register as a dependency. It will be instantiated  only when
            requested.
        singleton: If True, the service will be a singleton and instantiated only once.
        tags: Iterable of :py:class:`~.._providers.tag.Tag` applied to the service.

    Returns:
        The class or the class decorator.

    """

    def reg(cls: C) -> C:
        from ._service import _configure_service

        if issubclass(cls, Service):
            raise DuplicateDependencyError(f"{cls} is already defined as a dependency "
                                           f"by inheriting {Service}")

        _configure_service(cls,
                           conf=Service.Conf(wiring=None,
                                             singleton=singleton,
                                             tags=tags))

        return cast(C, cls)

    return klass and reg(klass) or reg
