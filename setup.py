import os
import pathlib

from setuptools import Extension, find_packages, setup

here = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))

with open(str(here / 'README.rst'), 'r') as f:
    readme = f.read()

ext_modules = []
install_requires = [
    'typing_extensions; python_version < "3.9.0"'
]

# Ideally this would be done with a installation flag...
if os.environ.get("ANTIDOTE_COMPILED") == "true":
    install_requires.append('fastrlock>=0.5,<0.6')

    from Cython.Build import cythonize
    from Cython.Compiler import Options

    cython_options = set(os.environ.get("ANTIDOTE_CYTHON_OPTIONS", "").split(","))
    extension_extras = {}
    cythonize_extras = {}

    if "annotate" in cython_options:
        Options.annotate = True
        cythonize_extras['annotate'] = True

    if "debug" in cython_options:
        cythonize_extras['gdb_debug'] = True

    if "trace" in cython_options:
        directive_defaults = Options.get_directive_defaults()
        directive_defaults['linetrace'] = True
        directive_defaults['binding'] = True
        extension_extras['define_macros'] = [('CYTHON_TRACE', '1')]


    def generate_extensions():
        extensions = []
        for root, _, filenames in os.walk('src'):
            for filename in filenames:
                if filename.endswith('.pyx'):
                    path = os.path.join(root, filename)
                    module = path[4:].replace('/', '.').rsplit('.', 1)[0]
                    extensions.append(Extension(module, [path], language='c++',
                                                **extension_extras))

        return extensions


    ext_modules = cythonize(generate_extensions(),
                            compiler_directives=dict(language_level=3,
                                                     boundscheck=False,
                                                     wraparound=False,
                                                     annotation_typing=False,
                                                     cdivision=True),
                            **cythonize_extras)

setup(
    name='antidote',
    use_scm_version=dict(write_to="src/antidote/_internal/scm_version.py"),
    description='Dependency injection.',
    long_description=readme,
    author='Benjamin Rabier',
    url='https://github.com/Finistere/antidote',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={"antidote": ["py.typed"]},
    include_dirs=["src"],
    ext_modules=ext_modules,
    python_requires='>=3.6,<4',
    install_requires=install_requires,
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    keywords='dependency injection',
    zip_safe=False,
)
