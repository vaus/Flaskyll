"""
Flaskyll
--------

Flaskyll is a little static website generator similar to Github's Jekyll
but implemented in Python, using Flask and Frozen-Flask.

It's main selling points are live, lazy, cached auto-regeneration with a
built-in web server and powerful pagination options.

Copyright (c) 2012 by vaus.
License: BSD, see LICENSE for more details.
"""

from setuptools import setup, find_packages


setup(
    name='Flaskyll',
    version='0.1',
    url='http://bitbucket.org/vaus/flaskyll',
    license='BSD',
    author='vaus',
    author_email='vaus@gmx.us',
    description='A Jekyll-like generator based on Flask',
    long_description=__doc__,
    packages=find_packages(),
    zip_safe=False,
    platforms='any',
    scripts = ['scripts/flaskyll.py'],
    install_requires=[
        'Flask',
        'Frozen-Flask',
        'Markdown',
        'PyYaml',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
    ]
)

