# flake8: noqa
# Ignoring F811 for multiple definitions

def test_readme_simple():
    import sys
    from antidote import (inject, Service, Constants, const, world, Provide,
                          Get, auto_provide)
    if sys.version_info < (3, 9):
        from typing_extensions import Annotated  # Python <= 3.8
    else:
        from typing import Annotated  # Python 3.9+

    class Conf(Constants):
        DB_HOST = const[str]('host')
        DB_HOST_WITHOUT_TYPE_HINT = const('host')

        def __init__(self):
            self._data = {'host': 'localhost:6789'}

        # Used to retrieve lazily the const, so injecting Conf.DB_HOST is equivalent to
        # having Conf().get('host')
        def get(self, key: str):
            return self._data[key]

    class Database(Service):  # Defined as a Service, so injectable.
        @inject
        def __init__(self, host: Annotated[str, Get(Conf.DB_HOST)]):
            self._host = host  # <=> Conf().get('host')

        # without PEP-593
        @inject(dependencies={'host': Conf.DB_HOST})
        def __init__(self, host: str):
            self._host = host  # <=> Conf().get('host')

    @inject  # Nothing is injected implicitly.
    def f(db: Provide[Database] = None):
        # Defaulting to None allows for MyPy compatibility but isn't required to work.
        assert db is not None
        pass

    f()  # works !
    f(Database('localhost:6789'))  # but you can still use the function normally

    # without PEP-593
    # With auto_provide=True, class type hints will be treated as dependencies.
    @inject(auto_provide=True)
    def f(db: Database = None):
        assert db is not None
        pass

    # For simplicity an alias for @inject(auto_provide=True) exists:
    @auto_provide
    def f(db: Database = None):
        assert db is not None
        pass

    # You can also retrieve dependencies by hand
    world.get(Conf.DB_HOST)
    world.get[str](Conf.DB_HOST)  # with type hint
    # if the dependency is the type itself, you may omit it:
    world.get[Database]()

    # If you need to handle multiple hosts for some reason you can
    # specify them in the dependency itself. As Database returns, by default,
    # a singleton this will also be the case here. Using the same host, will
    # return the same instance.
    world.get[Database](Database._with_kwargs(host='XX'))


def test_readme():
    """
    Simple example where a MovieDB interface is defined which can be used
    to retrieve the best movies. In our case the implementation uses IMDB
    to dot it.
    """
    import sys

    from antidote import (Constants, factory, inject, world, const, Service,
                          implementation, ProvideArgName, Get, From)
    if sys.version_info < (3, 9):
        from typing_extensions import Annotated  # Python <= 3.8
    else:
        from typing import Annotated  # Python 3.9+

    class MovieDB:
        """ Interface """

        def get_best_movies(self):
            pass

    class ImdbAPI:
        """ Class from an external library. """

        def __init__(self, *args, **kwargs):
            pass

    world.singletons.add('conf_path', '/etc/app.conf')

    class Conf(Constants):
        IMDB_HOST = const[str]('imdb.host')
        # Constants will by default automatically enforce the cast to int,
        # float and str. Can be removed or extended to support Enums.
        IMDB_PORT = const[int]('imdb.port')
        # But specifying a type is not required at all, it's mostly to help Mypy.
        IMDB_API_KEY = const('imdb.api_key')

        @inject(use_names=True)  # injecting world.get('conf_path')
        def __init__(self, conf_path: ProvideArgName[str]):
            """ Load configuration from `conf_path` """
            self._raw_conf = {
                'imdb': {
                    'host': 'dummy_host',
                    'api_key': 'dummy_api_key',
                    'port': '80'
                }
            }

        def get(self, key: str):
            from functools import reduce
            # self.get('a.b') <=> self._raw_conf['a']['b']
            return reduce(dict.get, key.split('.'), self._raw_conf)  # type: ignore

    # Provides ImdbAPI, as defined by the return type annotation.
    @factory
    @inject
    def imdb_factory(host: Annotated[str, Get(Conf.IMDB_HOST)],
                     port: Annotated[int, Get(Conf.IMDB_PORT)],
                     api_key: Annotated[str, Get(Conf.IMDB_API_KEY)]
                     ) -> ImdbAPI:
        # Here host = Conf().get('imdb.host')
        return ImdbAPI(host=host, port=port, api_key=api_key)

    # Without PEP-593
    @factory
    @inject(dependencies=(Conf.IMDB_HOST, Conf.IMDB_PORT, Conf.IMDB_API_KEY))
    def imdb_factory(host: str, port: int, api_key: str) -> ImdbAPI:
        # Here host = Conf().get('imdb.host')
        return ImdbAPI(host=host, port=port, api_key=api_key)

    @implementation(MovieDB)
    def current_movie_db():
        return IMDBMovieDB  # dependency to be provided for MovieDB

    class IMDBMovieDB(MovieDB, Service):
        # New instance each time
        __antidote__ = Service.Conf(singleton=False)

        @inject
        def __init__(self, imdb_api: Annotated[ImdbAPI, From(imdb_factory)]):
            self._imdb_api = imdb_api

        # Without PEP-593
        @inject(dependencies={'imdb_api': ImdbAPI @ imdb_factory})
        def __init__(self, imdb_api: ImdbAPI):
            self._imdb_api = imdb_api

        def get_best_movies(self):
            pass

    @inject
    def f(movie_db: Annotated[MovieDB, From(current_movie_db)] = None):
        assert movie_db is not None  # for Mypy
        pass

    # Without PEP-593
    @inject(dependencies=[MovieDB @ current_movie_db])
    def f(movie_db: MovieDB = None):
        assert movie_db is not None
        pass

    f()

    conf = Conf('/path')
    f(IMDBMovieDB(imdb_factory(
        # The class attributes will retrieve the actual value when called on a instance.
        # Hence this is equivalent to conf.get('imdb.host'), making your tests easier.
        host=conf.IMDB_HOST,
        port=conf.IMDB_PORT,
        api_key=conf.IMDB_API_KEY,  # <=> conf.get('imdb.api_key')
    )))

    # When testing you can also override locally some dependencies:
    with world.test.clone(keep_singletons=True):
        world.test.override.singleton(Conf.IMDB_HOST, 'other host')
        f()

    # If you encounter issues you can ask Antidote for a summary of what's happening
    # for a specific dependency. It becomes useful as an cycle/instantiation error
    # deep within the dependency tree results in a complex error stack.
    world.debug(f)
    """
    f
    └── Permanent implementation: MovieDB @ current_movie_db
        └──<∅> IMDBMovieDB
            └── ImdbAPI @ imdb_factory
                └── imdb_factory
                    ├── Const: Conf.IMDB_API_KEY
                    │   └── Conf
                    │       └── Singleton: 'conf_path' -> '/etc/app.conf'
                    ├── Const: Conf.IMDB_PORT
                    │   └── Conf
                    │       └── Singleton: 'conf_path' -> '/etc/app.conf'
                    └── Const: Conf.IMDB_HOST
                        └── Conf
                            └── Singleton: 'conf_path' -> '/etc/app.conf'

    Singletons have no scope markers.
    <∅> = no scope (new instance each time)
    <name> = custom scope
    """
