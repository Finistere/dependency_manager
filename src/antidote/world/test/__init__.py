"""
Testing utilities with Antidote. Also used by Antidote itself.
"""
from . import override
from ._methods import clone, empty, maybe_provide_from, new

__all__ = ['override', 'clone', 'new', 'empty', 'maybe_provide_from']
