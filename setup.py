from distutils.util import convert_path
from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))
metadata = dict()
with open(convert_path('src/xnt/version.py')) as metadata_file:
    exec(metadata_file.read(), metadata)

setup(
    name='python-fix-api',
    version=metadata['__version__'],
    zip_safe=False,

    description='Libraries to work with external XNT FIX bridges',

    author='XNT Ltd.',
    author_email='',
    url='https://exante.eu',

    license='GPL',

    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        "xnt": ["config/*.xml", "config/*.conf"]
    },

    install_requires=[
        'ujson==1.35',
        'deepdiff>=4.0.5',
        'inflection==0.3.1',
        'quickfix==1.15.1'
    ]
)
