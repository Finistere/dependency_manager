from typing import TypeVar

from ._compatibility.typing import Annotated
from .core.annotations import Ignore, Get, From, FromArg, FromArgName

__all__ = ['Ignore', 'Get', 'From', 'FromArg', 'FromArgName', 'UseArgName']

T = TypeVar('T')

# API.public
UseArgName = Annotated[T, FromArgName("{arg_name}")]  # type: ignore
UseArgName.__doc__ = """
The name of the argument will be used as the dependency.
"""
