import itertools
from inspect import getattr_static

import pytest

from antidote._internal.argspec import Argument, Arguments


def f(a: str, b, c: int = 1):
    pass


def g(a: list, *args):
    pass


def h(b=None, **kwargs):
    pass


def k():
    pass


class Dummy:
    def f(self, a: str, b=1, *args, **kwargs):
        pass

    @classmethod
    def g(cls, a):
        pass

    @staticmethod
    def h():
        pass


dummy = Dummy()


def lazy(dummy: 'Dummy'):
    pass


@pytest.mark.parametrize(
    'func,expected',
    [
        pytest.param(
            f,
            Arguments(
                arguments=tuple([
                    Argument('a', False, str),
                    Argument('b', False, None),
                    Argument('c', True, int),
                ]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='f'
        ),
        pytest.param(
            g,
            Arguments(
                arguments=tuple([
                    Argument('a', False, list),
                ]),
                has_var_positional=True,
                has_var_keyword=False,
                has_self=False
            ),
            id='g'
        ),
        pytest.param(
            h,
            Arguments(
                arguments=tuple([
                    Argument('b', True, None),
                ]),
                has_var_positional=False,
                has_var_keyword=True,
                has_self=False
            ),
            id='h'
        ),
        pytest.param(
            k,
            Arguments(
                arguments=tuple([]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='k'
        ),
        pytest.param(
            lazy,
            Arguments(
                arguments=tuple([
                    Argument('dummy', False, Dummy),
                ]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='lazy'
        ),
        pytest.param(
            Dummy.f,
            Arguments(
                arguments=tuple([
                    Argument('self', False, None),
                    Argument('a', False, str),
                    Argument('b', True, None),
                ]),
                has_var_positional=True,
                has_var_keyword=True,
                has_self=True
            ),
            id='cls.f'
        ),
        pytest.param(
            Dummy.g,
            Arguments(
                arguments=tuple([
                    Argument('a', False, None),
                ]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='cls.g'
        ),
        pytest.param(
            getattr_static(Dummy, 'g'),
            Arguments(
                arguments=tuple([
                    Argument('cls', False, None),
                    Argument('a', False, None),
                ]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=True
            ),
            id='cls.g'
        ),
        pytest.param(
            Dummy.h,
            Arguments(
                arguments=tuple([]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='cls.h'
        ),
        pytest.param(
            dummy.f,
            Arguments(
                arguments=tuple([
                    Argument('a', False, str),
                    Argument('b', True, None),
                ]),
                has_var_positional=True,
                has_var_keyword=True,
                has_self=False
            ),
            id='instance.f'
        ),
        pytest.param(
            dummy.g,
            Arguments(
                arguments=tuple([
                    Argument('a', False, None),
                ]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='instance.g'
        ),
        pytest.param(
            dummy.h,
            Arguments(
                arguments=tuple([]),
                has_var_positional=False,
                has_var_keyword=False,
                has_self=False
            ),
            id='instance.h'
        ),
    ]
)
def test_from_callable(func, expected: Arguments):
    result = Arguments.from_callable(func)
    assert isinstance(result, Arguments)
    assert expected.has_var_positional == result.has_var_positional
    assert expected.has_var_keyword == result.has_var_keyword

    for expected_arg, result_arg in zip(expected, result):
        assert expected_arg.name == result_arg.name
        assert expected_arg.has_default == result_arg.has_default
        assert expected_arg.type_hint == result_arg.type_hint

    for expected_arg in expected:
        assert expected_arg.name in result

        result_arg = result[expected_arg.name]
        assert expected_arg.name == result_arg.name
        assert expected_arg.has_default == result_arg.has_default
        assert expected_arg.type_hint == result_arg.type_hint


@pytest.mark.parametrize(
    'descriptor',
    [staticmethod, classmethod]
)
def test_from_methods(descriptor):
    def f(a, b=None):
        pass

    expected = Arguments.from_callable(f)
    result = Arguments.from_callable(descriptor(f))

    for expected_arg, result_arg in zip(expected, result):
        assert expected_arg.name == result_arg.name
        assert expected_arg.has_default == result_arg.has_default
        assert expected_arg.type_hint == result_arg.type_hint


args = tuple([
    Argument('x', False, int),
    Argument('y', True, str),
    Argument('z', False, float),
])


def test_getitem():
    arguments = Arguments(
        arguments=args,
        has_var_keyword=False,
        has_var_positional=False,
        has_self=False
    )
    assert arguments['x'] is args[0]
    assert arguments[1] is args[1]
    assert arguments.arg_names == {'x', 'y', 'z'}

    with pytest.raises(TypeError):
        arguments[2.3]


def test_without_self():
    for has_var_keyword, has_var_positional in itertools.product([True, False],
                                                                 [True, False]):
        arguments = Arguments(
            arguments=args,
            has_var_keyword=has_var_keyword,
            has_var_positional=has_var_positional,
            has_self=True
        )
        assert tuple(arguments.without_self) == args[1:]
        assert arguments.without_self.has_var_keyword == arguments.has_var_keyword
        assert arguments.without_self.has_var_positional == arguments.has_var_positional

    arguments = Arguments(
        arguments=args,
        has_var_keyword=False,
        has_var_positional=False,
        has_self=False
    )
    assert arguments.without_self is arguments


def test_magic_methods_arguments():
    arguments = Arguments(
        arguments=args,
        has_var_keyword=False,
        has_var_positional=False,
        has_self=False
    )
    assert 'x' in arguments
    assert 'unknown' not in arguments
    assert 3 == len(arguments)
    assert args == tuple(arguments)
    assert "x:int" in repr(arguments)
    assert "y:str =" in repr(arguments)
    assert "z:float" in repr(arguments)

    arguments_var_args = Arguments(
        arguments=args,
        has_var_keyword=False,
        has_var_positional=True,
        has_self=False
    )
    assert "x:int" in repr(arguments_var_args)
    assert "y:str =" in repr(arguments_var_args)
    assert "z:float" in repr(arguments_var_args)
    assert "*args" in repr(arguments_var_args)

    arguments_var_kwargs = Arguments(
        arguments=args,
        has_var_keyword=True,
        has_var_positional=False,
        has_self=False
    )
    assert "x:int" in repr(arguments_var_kwargs)
    assert "y:str =" in repr(arguments_var_kwargs)
    assert "z:float" in repr(arguments_var_kwargs)
    assert "**kwargs" in repr(arguments_var_kwargs)


def test_invalid_callable():
    with pytest.raises(TypeError):
        Arguments.from_callable(object())


def test_repr_argument():
    arg = Argument(name='x', has_default=True, type_hint=int,
                   type_hint_with_extras='found me!')
    assert 'x:int =' in repr(arg)
    assert arg.type_hint_with_extras in repr(arg)
