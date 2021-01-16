import sys

# Annotation
if sys.version_info < (3, 7):
    from typing import Callable, get_type_hints as _get_type_hints, cast
    from typing_extensions import Annotated, AnnotatedMeta

    # All of this is brittle, only working in our limited use case.
    def get_type_hints(obj: Callable[..., object], *, include_extras=False) -> object:
        # annotations cannot be removed in Python 3.6
        return _get_type_hints(obj)

    def get_origin(tp: object) -> object:
        if isinstance(tp, AnnotatedMeta):
            return Annotated
        return getattr(tp, "__origin__", None)

    def get_args(tp: object) -> tuple:
        return cast(tuple, getattr(tp, "__args__", tuple()))

elif sys.version_info < (3, 9):
    # get_origin and get_args must be retrieved from typing_extensions even for Python
    # 3.8 as the typing 3.8 implementation is not annotation-aware
    from typing_extensions import Annotated, get_type_hints, get_origin, get_args
else:
    from typing import Annotated, get_type_hints, get_origin, get_args

# Final / Protocol
if sys.version_info < (3, 8):
    from typing_extensions import final, Protocol
else:
    from typing import final, Protocol

# GenericMeta
if sys.version_info < (3, 7):
    from typing import GenericMeta
else:
    class GenericMeta(type):
        pass

__all__ = ['final', 'Protocol', 'GenericMeta', 'Annotated', 'get_type_hints',
           'get_origin', 'get_args']
