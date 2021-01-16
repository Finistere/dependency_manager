from typing import Optional, Union, Callable, TypeVar

import pytest

from antidote._compatibility.typing import Annotated
from antidote._internal.argspec import Arguments
from antidote.annotations import UseArgName, FromArg, FromArgName, Get
from antidote.core.annotations import extract_argument_dependency, AntidoteAnnotation, \
    extract_annotated_dependency, From

T = TypeVar('T')


class Dummy:
    pass


class Maker:
    def __rmatmul__(self, other):
        assert other is Dummy
        return Maker


def test_invalid_from_arg():
    with pytest.raises(TypeError, match=".*function.*"):
        FromArg(object())


def test_invalid_from_arg_name():
    with pytest.raises(TypeError, match=".*string.*"):
        FromArgName(object())

    with pytest.raises(ValueError, match=".*{arg_name}.*"):
        FromArgName("test")


def test_simple():
    def g(x: UseArgName[Dummy]):
        pass

    arguments = Arguments.from_callable(g)
    assert extract_argument_dependency(arguments[0]) == 'x'


@pytest.mark.parametrize('type_hint,expected', [
    pytest.param(type_hint, expected,
                 id=str(type_hint).replace('typing.', '').replace(f"{__name__}.", ""))
    for type_hint, expected in [
        (Dummy, Dummy),
        (Annotated[Dummy, object()], Dummy),
        (str, None),
        (T, None),
        (Union[str, Dummy], None),
        (Union[str, Dummy, int], None),
        (Optional[Union[str, Dummy]], None),
        (Callable[..., Dummy], None),
        (UseArgName[Dummy], 'x'),
        (Annotated[Dummy, From(Maker())], Maker),
        (Annotated[Dummy, FromArg(lambda arg: arg.name * 2)], 'xx'),
        (Annotated[Dummy, FromArgName("conf:{arg_name}")], 'conf:x'),  # noqa: F722
        (Annotated[Dummy, Get('something')], 'something'),  # noqa: F821
    ]
])
def test_extract_argument_dependency(type_hint, expected):
    def f(x: type_hint):
        pass

    arguments = Arguments.from_callable(f)
    assert extract_argument_dependency(arguments[0]) == expected

    def g(x: type_hint = None):
        pass

    arguments = Arguments.from_callable(g)
    assert extract_argument_dependency(arguments[0]) == expected


@pytest.mark.parametrize('type_hint,expected', [
    pytest.param(type_hint, expected,
                 id=str(type_hint).replace('typing.', '').replace(f"{__name__}.", ""))
    for type_hint, expected in [
        (Annotated[Dummy, object()], Dummy),
        (str, str),
        (T, T),
        (Union[str, Dummy], Union[str, Dummy]),
        (Annotated[Dummy, From(Maker())], Maker),
        (Annotated[Dummy, Get('something')], 'something')  # noqa: F821
    ]
])
def test_extract_annotated_dependency(type_hint, expected):
    assert extract_annotated_dependency(type_hint) == expected


def test_multiple_antidote_annotations():
    type_hint = Annotated[Dummy, Get('dummy'), Get('dummy')]  # noqa: F821

    def f(x: type_hint):
        pass

    arguments = Arguments.from_callable(f)
    with pytest.raises(TypeError):
        extract_argument_dependency(arguments[0])

    with pytest.raises(TypeError):
        extract_annotated_dependency(type_hint)


def test_unknown_antidote_annotations():
    type_hint = Annotated[Dummy, AntidoteAnnotation()]

    def f(x: type_hint):
        pass

    arguments = Arguments.from_callable(f)
    with pytest.raises(TypeError):
        extract_argument_dependency(arguments[0])

    with pytest.raises(TypeError):
        extract_annotated_dependency(type_hint)


@pytest.mark.parametrize('type_hint', [
    pytest.param(type_hint,
                 id=str(type_hint).replace('typing.', '').replace(f"{__name__}.", ""))
    for type_hint in [
        UseArgName[Dummy],
        Annotated[Dummy, FromArg(lambda arg: arg.name * 2)],
        Annotated[Dummy, FromArgName("conf:{arg_name}")]  # noqa: F722
    ]
])
def test_argument_only_annotations(type_hint):
    with pytest.raises(TypeError):
        extract_annotated_dependency(type_hint)
