#!/usr/bin/env python
"""
This is a little static website generator similar to Github's Jekyll
but implemented in Python, using Flask and Frozen-Flask.

Copyright (c) 2012 by vaus.
License: BSD, see LICENSE for more details.
"""

from flask import Flask, render_template, abort
from flask_frozen import Freezer
from markdown import markdown

import datetime
import os
import os.path as op
import math
import time
import sys

start = time.clock()

# Since the script has the same name as the module
# we must drop the current path from sys.path:

sys.path.pop(0)
from flaskyll.yamlpages import YamlPages


# Create the Flask application and configure it.
# Re-create the config after overriding root_path
# to be able to use relative paths:

app = Flask(__name__)
app.root_path = os.getcwd()

app.config = app.make_config()
app.config.update({
    'DEBUG': True,
    'PORT': 8000,

    'FREEZER_DESTINATION': 'build',
    'FREEZER_REMOVE_EXTRA_FILES': True,

    'MARKDOWN_EXTENSIONS': ['codehilite', 'extra'],
    'PRUNNING': True,
    'VERBOSE': True,
})


# Load the user configuration:

if op.isfile('config.py'):
    app.config.from_pyfile('config.py')


# Import the Flask-Markdown extension, unless the
# user does not have it installed:

try:
    from flaskext.markdown import Markdown
    Markdown(app, extensions = app.config['MARKDOWN_EXTENSIONS'])
except ImportError:
    pass


# Load Pages, Posts and create the initial global context
# which will be used for all the templates.  For pages, the renderer
# yields the body as a Template, to avoid 'render_template_string' slowdown:

pages = YamlPages(
    root       = '.',
    extensions = set(['.html', '.xml']),
    prunning   = app.config['PRUNNING'],
    verbose    = app.config['VERBOSE'],
    renderer   = lambda t: app.jinja_env.from_string(t),
    excludes   = (
        'post/',
        'static/',
        'templates/',
        app.config['FREEZER_DESTINATION'] + '/'
    ),
)

posts = YamlPages(
    root       = 'post',
    extensions = set(['.markdown', '.md']),
    prunning   = app.config['PRUNNING'],
    verbose    = app.config['VERBOSE'],
    renderer   = lambda t: markdown(t, app.config['MARKDOWN_EXTENSIONS']),
)

context = {}


# Context variable management:

def build_base_context():
    """
    Process posts to extract categories and sort them by date.
    Return a dict that contains pages, posts and categories.

    Posts without date are skipped.
    Posts without categories are put into 'uncategorized'.
    """
    published = []
    categories = {}

    for post in posts:
        if 'date' in post.meta:
            published.append(post)

            if not isinstance(post.meta['date'], datetime.date):
                raise Exception("wrong date format: %s" % post.meta)

            if not 'categories' in post.meta:
                post.meta['categories'] = ['uncategorized']

            for category in post.meta['categories']:
                categories.setdefault(category, [])
                categories[category].append(post)

    published.sort(reverse = True, key = lambda post: post.meta['date'])
    return { 'pages': pages, 'posts': published, 'categories': categories }


# Pagination support.  Since it's quite tricky to debug user errors
# with metadata on pagination, I do a lot more checks here to provide
# useful error messages, instead of aborting with a 404:

def maybe_build_pager(meta, current):
    """
    Try to build a pagination dict based on the options selected on the
    page .meta properties, where 'current' is the page we want now.
    Otherwise, return None.
    """
    if 'paginate' in meta:
        action = meta['paginate']

        if action == 'posts':
            return build_posts_pager(meta, current)

        if action == 'categories':
            return build_categories_pager(meta, current)

    return None


def build_posts_pager(meta, current):
    """
    Try to paginate posts, either in a single category
    or in all the categories, when meta.category = None.
    """
    # paginate single or all?
    category = None
    if 'category' in meta:
        category = meta['category']

        if not category in context['categories']:
            raise Exception("pagination category does not exist: %s" % meta)
        else:
            posts = context['categories'][category]
    else:
        posts = context['posts']

    # parse items per page:
    perpage = None
    if 'perpage' in meta:
        perpage = meta['perpage']

        if not isinstance(perpage, int) or int(perpage) < 1:
            raise Exception("pagination: invalid perpage: %s" % meta)

    total = int(math.ceil(float(len(posts)) / perpage))

    # make sure 'current' is correct:
    try:
        current = int(current)
        assert current > 0 and current <= total
    except:
        raise Exception("pagination: invalid current page: %s" % current)

    # actual pagination:
    start = (current - 1) * perpage
    end = current * perpage

    return { 'page': current, 'total': total, 'posts': posts[start:end] }


def build_categories_pager(meta, current):
    """
    Try to paginate posts, where each page is a single category.
    """
    # when not a direct request don't build the pager:
    if not isinstance(current, unicode):
        return None

    # make sure to do it in order:
    categories = sorted(context['categories'].iterkeys())

    if not current in categories:
        raise Exception("pagination: category does not exist: %s" % (current))

    total = len(categories)
    posts = context['categories'][current]

    return { 'page': current, 'total': total, 'posts': posts }


# Prepare the initial context, and set a function
# that will reload it in DEBUG mode (that is, when not freezing):

context = build_base_context()

def reload_context_on_debug():
    if app.config['DEBUG']:
        pages.load_pages()
        posts.load_pages()
        context.clear()
        context.update(build_base_context())


# Routes.
# Selected as best as possible to avoid conflict with each other
# to the extent where that's feasible:

@app.route('/')
@app.route('/<path:path>.xml')
@app.route('/<path:path>.html')
@app.route('/<path:path>/<current>/')
def page(path = 'index', current = 1):
    reload_context_on_debug()
    page = pages[path] or abort(404)

    # pagination enabled?
    if 'paginate' in page.meta:
        pager = maybe_build_pager(page.meta, current)
        if pager:
            return page.body.render(page = page, pager = pager, **context)

    # simple page:
    return page.body.render(page = page, **context)


@app.route('/post/<path:path>.html')
def post(path):
    reload_context_on_debug()
    post = posts[path] or abort(404)

    # does the post specify a template?
    if 'template' in post:
        template = post['template']
    else:
        template = 'post.html'

    return render_template(template, post = post, **context)


# Hook Frozen-Flask to avoid: .git, .hg, .hgignore etc...
# so that Flaskyll can be used both from and to repositories:

import flask_frozen
from flask_frozen import walk_directory

def without_dotted_folders(root):
    return [it for it in walk_directory(root) if not it.startswith('.')]

flask_frozen.walk_directory = without_dotted_folders


# Command-line:

if len(sys.argv) > 1 and sys.argv[1] == 'freeze':
    app.config['DEBUG'] = False
    Freezer(app).freeze()
    print time.clock() - start
else:
    app.run(debug = app.config['DEBUG'], port = app.config['PORT'])

