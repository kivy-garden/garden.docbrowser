"""
DocBrowser package.
Browser for view documentation of Python modules

Package Structure
=================

Modules:

* __init__.py: API imports

* docbrowser.py: classes of the widget and the stand-alone app

"""

try:
    from .docbrowser import DocBrowser, DocBrowserApp
except:
    from docbrowser import DocBrowser, DocBrowserApp

__author__ = 'ophermit'

__version__ = '0.1.0'
