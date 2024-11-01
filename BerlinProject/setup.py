from setuptools import setup, find_packages

setup(
    name='BerlinProject',
    version='0.1.0',
    include_package_data=True,
    description='Python implementation of MLF-TA',
    author='Loran Friedrich',
    author_email='loran.friedrich@gmail.com',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),  # would be the same as name
    install_requires=['wheel']
)