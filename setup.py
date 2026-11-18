from setuptools import setup

with open('README.md') as f:
    readme = f.read()

setup(
    name='dickson-secret-santa',
    version='0.2',
    description='Dickson Secret Santa Picker',
    long_description_content_type='text/markdown',
    long_description=readme,
    author='Liam Dickson',
    author_email='liamsongdickson@gmail.com',
    url='https://github.com/shiift/dickson-secret-santa',
    license='Apache Software License',
    packages=['dickson_secret_santa'],
    python_requires='>=3.10',
    keywords=['secret santa', 'gift exchange'],
    entry_points={
        'console_scripts': [
            'dickson_secret_santa=dickson_secret_santa.__main__:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Environment :: Console',
        'Programming Language :: Python :: 3',
    ],
    zip_safe=False,
)
