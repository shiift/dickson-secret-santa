# -*- coding: utf-8 -*-

from setuptools import setup


with open('README.md') as f:
    readme = f.read()

setup(
    name='dickson-secret-santa',
    version='0.1',
    description='Dickson Secret Santa Picker',
    long_description_content_type='text/markdown',
    long_description=readme,
    author='Liam Dickson',
    author_email='liamsongdickson@gmail.com',
    url='https://github.com/shiift/dickson-secret-santa',
    license='Apache Software License',
    packages=['dickson-secret-santa'],
    keywords=['secret santa', 'gift exchange',],
    entry_points={
        'console_scripts': [
            'dickson_secret_santa=dickson_secret_santa.__main__:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Environment :: Console',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    zip_safe=False,
)
