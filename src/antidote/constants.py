import collections.abc as c_abc
from typing import Any, FrozenSet, Iterable, Optional, Sequence, Union

from ._compatibility.typing import final
from ._constants import ConstantsMeta, MakeConst
from ._internal import API
from ._internal.utils import Copy, FinalImmutable
from .core.wiring import Wiring, WithWiringMixin

const = MakeConst()


@API.public
class Constants(metaclass=ConstantsMeta, abstract=True):
    """
    Used to declare constants, typically configuration. The purpose is to make common
    configuration manipulation easy. If you need complex operations, consider using the
    Constants class as a service by specifying :code:`public=True`.

    Constants are defined using :py:func:`.const`. It accepts a single value which will
    be given to :code:`get()`. You may also specify the type of the constants. If the
    type is included in :code:`auto_cast`, the cast will be enforced. By default it is
    only applied to :code:`str`, :code:`float` and :code:`int`.

    .. doctest:: helpers_Constants_v2

        >>> from antidote import Constants, const, world
        >>> class Config(Constants):
        ...     PORT = const[int]('80')
        ...     PORT_2 = const('8080')
        ...     DUMMY = const[dict]('dummy')
        ...
        ...     def get(self, value):
        ...         return value
        >>> # Mypy will treat it as a int AND it'll be cast to int.
        ... Config().PORT
        80
        >>> world.get(Config.PORT)
        80
        >>> Config().PORT_2
        '8080'
        >>> world.get(Config.PORT_2)
        '8080'
        >>> # Mypy will treat it as a dict but it'll not be cast to anything
        ... Config().DUMMY
        'dummy'

    """

    @final
    class Conf(FinalImmutable, WithWiringMixin):
        """
        Immutable constants configuration. To change parameters on a existing instance,
        use either method :py:meth:`.copy` or
        :py:meth:`~.core.wiring.WithWiringMixin.with_wiring`.
        """
        __slots__ = ('wiring', 'auto_cast')
        wiring: Optional[Wiring]
        auto_cast: FrozenSet[type]

        def __init__(self,
                     *,
                     auto_cast: Union[Iterable[type], bool] = True,
                     wiring: Optional[Wiring] = Wiring()):
            """
            Args:
                wiring: :py:class:`Wiring` used on the class. Defaults to wire only
                    :code:`__init__()`.
                auto_cast: When the type of the constant is specified with
                    :py:func:`.const`, the value of the dependency will be cast to its
                    type if it's one of :code:`str`, :code:`float` or :code:`int` by
                    default. You can disable this by specifying code:`auto_cast=False` or
                    change the types for which it's done by specifying explicitly those
                    types.
            """
            if not (wiring is None or isinstance(wiring, Wiring)):
                raise TypeError(f"wiring can be None or a Wiring, "
                                f"but not a {type(wiring)}")

            if isinstance(auto_cast, bool):
                if auto_cast:
                    auto_cast = frozenset((float, int, str))
                else:
                    auto_cast = frozenset()
            elif isinstance(auto_cast, c_abc.Iterable):
                auto_cast = frozenset(auto_cast)
                if not all(isinstance(tpe, type) for tpe in auto_cast):
                    raise TypeError("auto_cast must a boolean or a iterable of types")
            else:
                raise TypeError("auto_cast must a boolean or a iterable of types")

            super().__init__(wiring=wiring, auto_cast=auto_cast)

        def copy(self,
                 *,
                 wiring: Union[Optional[Wiring], Copy] = Copy.IDENTICAL,
                 auto_cast: Union[Union[Sequence[type], bool], Copy] = Copy.IDENTICAL
                 ) -> 'Constants.Conf':
            """
            Copies current configuration and overrides only specified arguments.
            Accepts the same arguments as :py:meth:`.__init__`
            """
            return Copy.immutable(self, wiring=wiring, auto_cast=auto_cast)

    __antidote__: Conf = Conf()

    def get(self, key: Any) -> object:
        raise NotImplementedError()
