import pytest

from antidote import wire, world


@pytest.fixture(autouse=True)
def new_world():
    with world.test.empty():
        yield


@pytest.mark.parametrize('obj', [object(), lambda: None])
def test_invalid_class(obj):
    with pytest.raises(TypeError):
        wire(obj)


@pytest.mark.parametrize(
    'kwargs',
    [dict(methods=object()),
     dict(auto_provide=object()),
     dict(use_names=object()),
     dict(dependencies=object())]
)
def test_invalid_type(kwargs):
    with pytest.raises(TypeError):
        @wire(**kwargs)
        class Dummy:
            pass
