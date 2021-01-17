import enum
from typing import TypeVar

from .debug import debug_repr, short_id
from .immutable import FinalImmutable, Immutable
from .meta import AbstractMeta, FinalMeta
from .slots import SlotRecord
from .. import API

Im = TypeVar('Im', bound=Immutable)


@API.private
class Default(enum.Enum):
    sentinel = enum.auto()


@API.private
class Copy(enum.Enum):
    IDENTICAL = enum.auto()

    @staticmethod
    def immutable(current: Im, **kwargs: object) -> Im:
        return type(current)(**{
            attr: getattr(current, attr) if value is Copy.IDENTICAL else value
            for attr, value in kwargs.items()
        })


__all__ = ['debug_repr', 'short_id', 'FinalImmutable', 'Immutable', 'AbstractMeta',
           'FinalMeta', 'SlotRecord', 'API', 'Default', 'Copy']
