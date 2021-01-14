import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

if sys.version_info < (3, 8):
    from typing_extensions import final, Protocol
else:
    from typing import final, Protocol

if sys.version_info < (3, 7):
    from typing import GenericMeta
else:
    class GenericMeta(type):
        pass

__all__ = ['final', 'Protocol', 'GenericMeta', 'Annotated']
