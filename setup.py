#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

from setuptools import setup

try:
    from lib2to3 import refactor
    fixers = set(refactor.get_fixers_from_package('lib2to3.fixes'))
except ImportError:
    fixers = set()

with open('README') as readme:
    documentation = readme.read()

setup(
        name = 'shifter',
        version = '2.40',
        py_modules = ['shifter'],

        author = 'Terence Honles',
        author_email = 'terence@honles.com',
        description = 'Transmission RPC Bindings',
        long_description = documentation,
        license = 'PSF',
        keywords = 'Transmission RPC torrent',
        url = 'https://github.com/terencehonles/shifter',

        use_2to3 = True,
        # only use the following fixers (everything else is already compatible)
        use_2to3_exclude_fixers = fixers - set([
            'lib2to3.fixes.fix_future',
            'lib2to3.fixes.fix_reduce',
            'lib2to3.fixes.fix_urllib',
        ]),

        classifiers = [
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: Python Software Foundation License',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
            'Topic :: Software Development :: Libraries',
        ]
)
