"""
Module docbrowser.py
====================

Classes:

* DocBrowser: represents browser as a Kivy widget.

* DocBrowserApp: represents browser as a stand-alone app.


DocBrowser class
================

Subclass of :class:`~kivy.uix.boxlayout.BoxLayout`.
Represents the widget of a browser.

This widget shows you docstrings of specified Python module/package.
The widget is useful for monitoring the availability of documentation in the
code.

For example, place the following code in any module and run it::

    if __name__ == '__main__':
        from kivy.app import runTouchApp
        from docbrowser import DocBrowser
        runTouchApp(DocBrowser(module_name='__main__'))

It will show you documentation of the module, in which you put this example.
You can specify any other module name.

.. note::

    Please note that the module you want to see must be installed in the
    currently active virtual environment

By default, object inspector displays only the submodules and classes. By
changing appropriate properties you can:

* via :attr:`DocBrowser.functions` - enable/disable display of the module
  functions

* via :attr:`DocBrowser.imported` - enable/disable display of the imported
  modules

* via :attr:`DocBrowser.methods` - enable/disable display of the class methods

.. warning::

    :attr:`DocBrowser.methods` - is an experimental feature. It is strongly
    recommended DO NOT enable it if you trying to load documentation of a large
    module (such as "kivy").

The following example starts the "DocBrowser" with all available features::

    if __name__ == '__main__':
        from kivy.app import runTouchApp
        from docbrowser import DocBrowser
        runTouchApp(
            DocBrowser(module_name='__main__', functions=True,
                       imported=True, methods=True))

.. note::

    Please note that if you've changed docstrings you need to restart app to
    see the changes.


DocBrowserApp class
===================

The second possible way of usage - as a stand-alone app::

    from docbrowser import DocBrowserApp
    DocBrowserApp(module_name=__name__).run()

Also app can be started via shell (the module name is specified as a
parameter)::

    python docbrowser.py kivy.core

By the way, if you omit this parameter you will see documentation of the module
named "kivy"

"""

from kivy.compat import PY2
from kivy.properties import StringProperty, BooleanProperty, Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.treeview import TreeViewLabel, TreeView
from kivy.lang import Builder
from kivy.app import App
import inspect
from importlib import import_module
from kivy.garden.xpopup import XProgress, XError


__author__ = 'ophermit'


Builder.load_string('''
#:kivy 1.9.1
#:import metrics kivy.metrics

<ObjectInspectorLabel>:
    on_touch_down: self.parent.info.text = self.doc if\
        self.collide_point(*args[1].pos) and self.doc else\
        self.parent.info.text

<DocBrowser>:
    orientation: 'vertical'
    spacing: 5
    padding: [6, 6, 6, 6]
    BoxLayout:
        orientation: 'horizontal'
        spacing: 5
        Splitter:
            sizable_from: 'right'
            min_size: '200dp'
            size_hint: (.3, 1)
            id: splitter
            ScrollView:
                ObjectInspector:
                    id: inspector
                    info: document
                    module_name: root.module_name
                    imported: root.imported
                    methods: root.methods
                    functions: root.functions
                    size_hint_y: None
                    height: self.minimum_height
                    hide_root: True
        RstDocument:
            id: document
            size_hint_x: .8
            orientation: 'vertical'
            source_error: 'ignore'
    GridLayout:
        size_hint: (1, None)
        height: inp_module_name.line_height * 1.7
        cols: 2
        rows: 1
        spacing: [5]
        TextInput:
            id: inp_module_name
            text: root.module_name
            hint_text: 'Module name'
            multiline: False
            on_text_validate: root.load_doc()
            focus: True
        Button:
            id: btn_load
            size_hint_x: None
            width: metrics.dp(100)
            text: 'Load doc'
            on_release: root.load_doc()
''')

NO_DOC_STR = 'No documentation found'


class ObjectInspectorLabel(TreeViewLabel):
    """Represents a node in the object inspector. For internal use only.
    """

    doc = StringProperty('')
    '''Represents docstring.

    :attr:`doc` is a :class:`~kivy.properties.StringProperty` and
    defaults to ''.
    '''


class ObjectInspector(TreeView):
    """Object inspector class. For internal use only.
    """

    get_doc = lambda self, x: inspect.getdoc(x) or NO_DOC_STR
    '''Predicate to get docstrings
    '''

    def __init__(self, **kwargs):
        # generator object
        self.__gen = None
        # progressbar popup object
        self.__progress = None
        # already processed modules (for the circular detection)
        self.__submodules = []
        # root module node
        self.__root_module_node = None
        super(ObjectInspector, self).__init__(**kwargs)

    def _create_category_node(self, title, parent_node, count):
        """Creates and returns a new category node

        :param title: category title
        :param parent_node: parent node in the object's inspector tree
        :param count: sub-entries count
        :return: the newly created category node
        """
        return self.add_node(
            ObjectInspectorLabel(
                text='[ %s (%d) ]' % (title, count), no_selection=True),
            parent_node)

    def _fill_category_node(self, module, obj_filter, title, parent):
        """Creates and fills new category node. Used as a generator

        :param module: module/class object
        :param obj_filter: predicate to filter members
        :param title: category title
        :param parent: parent node in the object's inspector tree
        """
        members = inspect.getmembers(module, obj_filter)
        if not members:
            return

        category_node = self._create_category_node(title, parent, len(members))
        for entry in members:
            node = self.add_node(
                ObjectInspectorLabel(text=entry[0],
                                     doc=self.get_doc(entry[1])),
                category_node)

            # TODO::OPTIMIZE
            if self.methods:
                if PY2:
                    obj_filter = inspect.ismethod
                else:
                    # in Python 3.x inspect.ismethod returns []
                    obj_filter = inspect.isroutine
                for method in inspect.getmembers(entry[1], obj_filter):
                    self.add_node(
                        ObjectInspectorLabel(
                            text=method[0], doc=self.get_doc(method[1])),
                        node)
            yield

    def _create_module_node(self, module, parent=None):
        """Performs recursive module analysis. Used as a generator.

        :param module: object of module/submodule
        :param parent: parent node in the object's inspector tree
        """
        module_node = self.add_node(
            ObjectInspectorLabel(
                text='* %s' % module.__name__, doc=self.get_doc(module),
                is_open=not parent), parent)
        if not parent:
            self.__root_module_node = module_node

        # Checking for circular import
        if module.__name__ in self.__submodules:
            module_node.text += ' (circular)'
            return
        else:
            self.__submodules.append(module.__name__)
        yield

        # Processing the submodules
        pred_submodules = lambda x: inspect.ismodule(x)\
            and module.__name__ in x.__name__
        submodules = inspect.getmembers(module, pred_submodules)
        if submodules:
            submodule_node = self._create_category_node(
                'Submodules', module_node, len(submodules))
            for submodule in submodules:
                for entry in self._create_module_node(
                        submodule[1], submodule_node):
                    yield

        # Processing the module's members
        categories = [
            (True, 'Classes', lambda x: inspect.isclass(x)
                and x.__module__ == module.__name__),
            (self.functions, 'Functions', lambda x: inspect.isfunction(x)
                and x.__module__ == module.__name__),
            (self.imported, 'Imported', lambda x:
                (inspect.isclass(x) or inspect.isroutine(x))
                and x.__module__ != module.__name__)
        ]

        for ctgr in categories:
            if ctgr[0]:
                for step in self._fill_category_node(
                        module, ctgr[2], ctgr[1], module_node):
                    yield

    def _fill_tree(self, pdt=None):
        """The main loop of documentation collection.
        """
        if self.__progress and self.__progress.is_canceled():
            return

        try:
            next(self.__gen)
            Clock.schedule_once(self._fill_tree, .01)
        except StopIteration:
            self._load_complete()
        except Exception as e:
            XError(text=str(e))
            self._load_complete()

    def _load_complete(self):
        """Performing the final steps
        """
        self.info.text = self.__root_module_node.doc
        if self.__progress:
            self.__progress.complete(show_time=0, text='')
            self.__progress = None
        self.__gen = None

    def load_documentation(self, pdt=None):
        """Preparations for collecting documentation.
        """
        if self.module_name == '' or self.__gen is not None:
            return

        # importing specified module
        try:
            # DON`T REMOVE OR FOUND AND FIX THE ISSUE
            # module reloads, but documentation is not changed
            """
            if self.module_name in modules.keys()\
                    and self.module_name != '__main__':
                module = reload(modules[self.module_name])
            else:
            """
            module = import_module(self.module_name)
        except ImportError as e:
            XError(text=str(e))
            return
        except Exception as e:
            XError(text='Unexpected exception\nReason: %s' % str(e))
            return

        # clearing the tree
        self.__submodules[:] = []
        for node in self.iterate_all_nodes():
            self.remove_node(node)

        # starting the process
        self.__progress = XProgress(
            buttons=[],
            text='Loading documentation...',
            title='Module "%s"' % self.module_name)
        self.__progress.autoprogress()
        self.__gen = self._create_module_node(module)
        self._fill_tree()


class DocBrowser(BoxLayout):
    """
    DocBrowser widget class. See "docbrowser" module documentation for more
    information.
    """

    module_name = StringProperty(__name__)
    '''Represents module name. Use it to automatically load documentation when
    the widget created.

    :attr:`module_name` is a :class:`~kivy.properties.StringProperty` and
    defaults to __name__.
    '''

    functions = BooleanProperty(True)
    '''Enables/disables display of module functions in the object inspector.

    :attr:`functions` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to True.
    '''

    imported = BooleanProperty(False)
    '''Enables/disables display of imported modules in the object inspector.

    :attr:`module_name` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to False.
    '''

    methods = BooleanProperty(False)
    '''Enables/disables display of class methods in the object inspector.

    .. warning::

        This is an experimental feature. It is not recommended to turn it on if
        you trying to load documentation of a large module.

    :attr:`methods` is a :class:`~kivy.properties.BooleanProperty` and
    defaults to False.
    '''

    def __init__(self, **kwargs):
        super(DocBrowser, self).__init__(**kwargs)
        self.load_doc()

    def load_doc(self):
        """Callback for the "Load doc" button.
        """
        self.ids.inspector.module_name = self.ids.inp_module_name.text
        Clock.schedule_once(self.ids.inspector.load_documentation, .1)


class DocBrowserApp(App):
    """
    DocBrowser application class. See "docbrowser" module documentation for
    more information.
    """

    title = StringProperty('Documentation browser')
    '''Title of the app.
    '''

    module_name = StringProperty('')
    '''Represents module name. Use it to automatically load documentation when
    the app starts.
    '''

    def build(self):
        return DocBrowser(module_name=self.module_name)


if __name__ == '__main__':
    import sys
    import kivy
    kivy.require('1.9.1')

    module_name = 'kivy'
    if len(sys.argv) > 1:
        module_name = sys.argv[1]

    DocBrowserApp(module_name=module_name).run()
