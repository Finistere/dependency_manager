import builtins
import inspect
from typing import Union

from .annotations import (AntidoteAnnotation, From, FromArg, FromArgName, Get,
                          INJECT_SENTINEL)
from .injection import Arg
from .._compatibility.typing import Annotated, get_args, get_origin
from .._internal import API
from .._internal.argspec import Argument


@API.private
def extract_annotated_dependency(type_hint: object) -> object:
    origin = get_origin(type_hint)

    # Dependency explicitly given through Annotated (PEP-593)
    if origin is Annotated:
        args = get_args(type_hint)
        antidote_annotations = [a
                                for a in getattr(type_hint, "__metadata__", tuple())
                                if isinstance(a, AntidoteAnnotation)]
        if len(antidote_annotations) > 1:
            raise TypeError(f"Multiple AntidoteAnnotation are not supported. "
                            f"Found {antidote_annotations}")
        elif antidote_annotations:
            annotation: AntidoteAnnotation = antidote_annotations[0]
            if annotation is INJECT_SENTINEL:
                return args[0]
            elif isinstance(annotation, Get):
                return annotation.dependency
            elif isinstance(annotation, From):
                return args[0] @ annotation.source
            else:
                raise TypeError(f"Annotation {annotation} cannot be used"
                                f"outside of a function.")
        else:
            return args[0]

    return type_hint


_BUILTINS_TYPES = {e for e in builtins.__dict__.values() if isinstance(e, type)}


@API.private
def extract_annotated_arg_dependency(argument: Argument) -> object:
    type_hint = argument.type_hint_with_extras
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Optional
    if origin is Union:
        if len(args) == 2:
            if isinstance(None, args[1]) or isinstance(None, args[0]):
                type_hint = args[0] if isinstance(None, args[1]) else args[0]
                origin = get_origin(type_hint)
                args = get_args(type_hint)

    # Dependency explicitly given through Annotated (PEP-593)
    if origin is Annotated:
        antidote_annotations = [a
                                for a in type_hint.__metadata__
                                if isinstance(a, AntidoteAnnotation)]
        if len(antidote_annotations) > 1:
            raise TypeError(f"Multiple AntidoteAnnotation are not supported. "
                            f"Found {antidote_annotations}")
        elif antidote_annotations:
            # If antidote annotation, no additional check is done we just return
            # what was specified.
            annotation: AntidoteAnnotation = antidote_annotations[0]
            if annotation is INJECT_SENTINEL:
                return args[0]
            elif isinstance(annotation, Get):
                return annotation.dependency
            elif isinstance(annotation, From):
                return args[0] @ annotation.source
            elif isinstance(annotation, FromArg):
                arg = Arg(argument.name,
                          argument.type_hint,
                          argument.type_hint_with_extras)
                return annotation.function(arg)  # type: ignore
            elif isinstance(annotation, FromArgName):
                return annotation.template.format(arg_name=argument.name)
            else:
                raise TypeError(f"Unsupported AntidoteAnnotation, {type(annotation)}")

    return None


@API.private
def extract_auto_provided_arg_dependency(argument: Argument) -> object:
    type_hint = argument.type_hint_with_extras
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Optional
    if origin is Union:
        if len(args) == 2:
            if isinstance(None, args[1]) or isinstance(None, args[0]):
                type_hint = args[0] if isinstance(None, args[1]) else args[0]
                origin = get_origin(type_hint)
                args = get_args(type_hint)

    dependency = type_hint

    if origin is Annotated:
        antidote_annotations = [a
                                for a in type_hint.__metadata__
                                if isinstance(a, AntidoteAnnotation)]
        if not antidote_annotations:
            dependency = args[0]
        else:
            return None  # necessary for Python 3.6

    if (getattr(dependency, '__module__', '') != 'typing'
            and dependency not in _BUILTINS_TYPES
            and (isinstance(dependency, type) and inspect.isclass(dependency))):
        return dependency

    return None
