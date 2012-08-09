# -*- coding: utf-8 -*-
"""
    flaskyll.yamlpages
    ~~~~~~~~~~~~~~~~~~

    A reusable version of Flask-FlatPages that does not
    depend on Flask's `app.config` or Markdown.

    :copyright: (c) 2010 by Simon Sapin.
    :copyright: (c) 2012 by vaus.
    :license: BSD, see LICENSE for more details.
"""

from werkzeug import cached_property

import itertools
import os
import os.path as op
import posixpath
import yaml


try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class LazyYamlPage(object):
    """
    Represents a page that has a YAML header. The page :attr:`meta`
    and :attr:`body` are processed on access and then cached.

    :param path: Route in the web server where this page is located.

    :param meta: YAML header, unprocessed.

    :param body: Contents of this page, unprocessed.

    :param renderer: The function to call to process :attr:`body`.
    """
    def __init__(self, path, meta, body, renderer):
        self.path = path
        self.renderer = renderer

        self._meta = meta
        self._body = body

    @cached_property
    def meta(self):
        """
        Returns the dict of metadata parsed as YAML from the header
        of the page.
        """
        meta = yaml.load(self._meta, Loader = Loader) or {}

        assert isinstance(meta, dict)
        return meta

    @cached_property
    def body(self):
        """
        Returns the content of the page, as rendered through
        `self.renderer`.
        """
        return self.renderer(self._body)

    def __getitem__(self, key):
        """
        Shortcut for accessing metadata.

        ``page['title']`` or, in a template, ``{{ page.title }}`` are
        equivalent to ``page.meta['title']``.
        """
        return self.meta[key]

    def __iter__(self):
        """
        Iterate on all our meta properties.
        """
        return self.meta.iterkeys()


class YamlPages(object):
    """
    Parses and maintains a collection of files that have a YAML header,
    polling them for changes.  This is based on Flask-FlatPages_.
    This class does not depend on a global Flask app configuration and
    can thus be used multiple times in a single application.

    .. _Flask-FlatPages: http://http://packages.python.org/Flask-FlatPages/

    :param root: Folder in the filesystem to search for files.

    :param extensions: A set of file extensions to include in the search
        with the dot prefix, such as: ``set(['.html', '.xml'])``.

    :param prunning: Delete cached files that are no longer in the filesystem.

    :param verbose: Print cache management information.

    :param renderer: A function that will be called to process each page
        body when accessed.  The result is cached until the file changes.
        The default is a identity function.

    :param excludes: A tuple of `starting` path strings to ignore
        in the search.  Use posix path separators, relative from the root.

        Examples::

            '.'       ignores .hg/, .git/, .hgignore...
            'static/' ignores the 'static' folder at the root.

    :param encoding: Defaults to: `'utf8'`.
    """
    def __init__(self,
                 root,
                 extensions,
                 prunning = True,
                 verbose  = False,
                 renderer = lambda x: x,
                 excludes = (),
                 encoding = 'utf8'):

        self.root = root
        self.extensions = extensions
        self.prunning = prunning
        self.verbose = verbose
        self.renderer = renderer
        self.excludes = excludes
        self.encoding = encoding

        self._first_run = True
        self._file_cache = {}
        self._pages = {}

    def load_pages(self):
        """
        Walk the page root directory and collect all the pages
        that have changed since our last collection.
        """
        if self.prunning:
            self.prune_cache()

        self._pages.clear()
        for root, dirs, files in os.walk(self.root):
            for filename in files:
                filepath = op.join(root, filename)
                relpath = op.relpath(filepath, self.root)

                path, extension = op.splitext(relpath)
                path = path.replace(os.sep, posixpath.sep)

                if not path.startswith(self.excludes):
                    if extension in self.extensions:
                        self._load_page(path, filepath)

        self._first_run = False

    def parse_page(self, filepath):
        """
        Parse and return the meta and body parts of a given YAML file.
        This is the method to override to implement custom parsing.

        :param filepath: path to the file to parse.
        """
        with open(filepath) as fd:
            content = fd.read().decode(self.encoding)

            lines = iter(content.split(u'\n'))

            meta = u'\n'.join(itertools.takewhile(unicode.strip, lines))
            body = u'\n'.join(lines)

            return meta, body

    def prune_cache(self):
        """
        Delete pages in the file cache that are no longer
        in the filesystem.  This may reduce memory usage with a lot
        of pages.
        """
        for filepath in self._file_cache.keys():
            if not op.isfile(filepath):
                if self.verbose:
                    print " * Prunning: ", filepath
                del self._file_cache[filepath]

    def _load_page(self, path, filepath):
        mtime = op.getmtime(filepath)
        cached = self._file_cache.get(filepath)

        if cached and cached[1] == mtime:
            page = cached[0]
        else:
            if self.verbose and not self._first_run:
                print " * Loading:", filepath

            meta, body = self.parse_page(filepath)
            page = LazyYamlPage(path, meta, body, self.renderer)
            self._file_cache[filepath] = page, mtime

        self._pages[path] = page

    def __iter__(self):
        """
        Iterate on all pages.
        """
        if self._first_run:
            self.load_pages()

        return self._pages.itervalues()

    def __getitem__(self, path):
        """
        Return the specific page corresponding to `path` or `None`
        if it doesn't exist.
        """
        if self._first_run:
            self.load_pages()

        return self._pages.get(path)

