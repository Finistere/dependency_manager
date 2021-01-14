from antidote._internal.world import new_container
from antidote.core import Container


def test_new_container():
    assert isinstance(new_container(), Container)
