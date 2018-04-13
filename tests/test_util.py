import pytest

from antidote.utils import get_arguments_specification, rgetitem


def f(a, b, c=1):
    pass


def g(a, *args):
    pass


def h(b=None, **kwargs):
    pass


def k():
    pass


class Dummy(object):
    def f(self, a, b=1, *args, **kwargs):
        pass

    @classmethod
    def g(cls, a):
        pass

    @staticmethod
    def h():
        pass


d = Dummy()


@pytest.mark.parametrize(
    'func,expected',
    [
        (f, ([('a', False), ('b', False), ('c', True)], False, False)),
        (g, ([('a', False)], True, False)),
        (h, ([('b', True)], False, True)),
        (k, ([], False, False)),
        (Dummy.f, ([('self', False), ('a', False), ('b', True)], True, True)),
        (Dummy.g, ([('a', False)], False, False)),
        (Dummy.h, ([], False, False)),
        (d.f, ([('a', False), ('b', True)], True, True)),
        (d.g, ([('a', False)], False, False)),
        (d.h, ([], False, False)),
    ],
    ids=[
        'f', 'g', 'h', 'k',
        'cls.f', 'cls.g', 'cls.h',
        'instance.f', 'instance.g', 'instance.h'
    ]
)
def test_arg_spec(func, expected):
    assert expected == get_arguments_specification(func)


def test_rgetitem():
    data = {
        'data': {
            'key1': object()
        },
        'something': object(),
        'another': 'string'
    }

    assert data['something'] is rgetitem(data, ['something'])
    assert data['data']['key1'] is rgetitem(data, ['data', 'key1'])

    with pytest.raises(KeyError):
        rgetitem(data, ['data', 'nothing'])

    with pytest.raises(KeyError):
        rgetitem(data, ['another', 'random'])