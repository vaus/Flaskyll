# -*- coding: utf-8 -*-
"""
A reusable version of Flask-FlatPages that does not
depend on Flask's 'app.config' or Markdown.

Copyright (c) 2010 by Simon Sapin.
Copyright (c) 2012 by vaus.
License: BSD, see LICENSE for more details.
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


class YamlPage(object):
    """
    Represents a page that has a YAML header.
    Initialization parameters:

        path:
            Route in the web server where this page is located.

        meta:
            YAML header, to be processed/cached.
            The processed result will be cached in 'page.meta'.

        body:
            Contents of this page, to be processed/cached.
            The processed result will be cached in 'page.body'.

        renderer:
            A function that will be called to process the page
            body when accessed.
    """
    def __init__(self, path, meta, body, renderer):
        self.path = path
        self.renderer = renderer

        self._meta = meta
        self._body = body

    @cached_property
    def meta(self):
        """
        A dict of metadata parsed as YAML from the header of the page.
        """
        meta = yaml.load(self._meta, Loader = Loader) or {}

        assert isinstance(meta, dict)
        return meta

    @cached_property
    def body(self):
        """
        The content of the page, as rendered through self.renderer.
        """
        return self.renderer(self._body)

    def __getitem__(self, key):
        """
        Shortcut for accessing metadata.

        page['title'] or, in a template, {{ page.title }} are
        equivalent to page.meta['title'].
        """
        return self.meta[key]

    def __iter__(self):
        """
        Iterate on all our meta properties.
        """
        return self.meta.iterkeys()


class YamlPages(object):
    """
    Reads, parses and maintains a collection of files
    that have a YAML header, polling them for changes.

    Initialization parameters:

        root:
            Folder in the filesystem to search for files.

        extensions:
            A set of file extensions to include in the search
            with the dot prefix, such as: set(['.html', '.xml']).

        prunning:
            Delete cached files that are no longer in the filesystem
            on each reload.  The default is True.

        verbose:
            Print cache management information which may aid on debugging.
            The default is False.

        renderer:
            A function that will be called to process each page
            body when accessed.  The result is cached until the file changes.
            The default is a identity function.

        excludes:
            A tuple of *starting* path strings to ignore in the search.
            Use posix path separators, relative from the root.

            Examples:
                '.'       ignores .hg/, .git/, .hgignore...
                'static/' ignores the 'static' FOLDER at the root.
                'static'  ignores the 'static' FILE at the root.

        encoding:
            Defaults to: 'utf8'.
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

        for root, dirs, files in os.walk(self.root):
            for filename in files:
                filepath = op.join(root, filename)
                relpath = op.relpath(filepath, self.root)

                route, extension = op.splitext(relpath)
                route = route.replace(os.sep, posixpath.sep)

                if not route.startswith(self.excludes):
                    if extension in self.extensions:
                        self.load_page(route, filepath)

        self._first_run = False

    def load_page(self, route, filepath):
        """
        Load the page that corresponds to 'filepath'.

        If it is in the cache and the file hasn't changed, this does nothing.
        Otherwise, it reads the file and creates a page at 'route'.
        """
        mtime = op.getmtime(filepath)
        cached = self._file_cache.get(filepath)

        if cached and cached[1] == mtime:
            return

        if self.verbose and not self._first_run:
            print " * Loading:", filepath

        meta, body = self.parse_page(filepath)
        page = YamlPage(route, meta, body, self.renderer)

        self._file_cache[filepath] = page, mtime
        self._pages[route] = page

    def parse_page(self, filepath):
        """
        Parse and return the meta, body parts of a given file.
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
                    print " * Prunning:", filepath
                del self._file_cache[filepath]

    def __iter__(self):
        """
        Iterate on all pages.
        """
        if self._first_run:
            self.load_pages()

        return self._pages.itervalues()

    def __getitem__(self, route):
        """
        Return the page that lives at a specific route.
        """
        if self._first_run:
            self.load_pages()

        try:
            return self._pages[route]
        except KeyError:
            return None

