__import__("pkg_resources").declare_namespace(__name__)

import os
import zc.recipe.egg
import mock
from infi.pyutils.decorators import wraps
from infi.pyutils.contexts import contextmanager
from .lazy_imports import LazyImportsWorkaroundMixin, LazyImportMixin
from .windows import WindowsWorkaroundMixin

is_windows = os.name == 'nt'


class Workaround(LazyImportsWorkaroundMixin, WindowsWorkaroundMixin):
    def __init__(self, recipe, gui=False):
        super(Workaround, self).__init__(recipe, gui)

    def __call__(self, func):
        @wraps(func)
        def callee(*args, **kwargs):
            installed_files = func(*args, **kwargs)
            self._apply_windows_workarounds(installed_files)
            self._apply_lazy_imports(installed_files)
            return installed_files
        return callee


class AbsoluteExecutablePathMixin(object):
    def is_relative_paths_option_set(self):
        relative_paths = self.options.get('relative-paths',
                                          self.buildout.get('buildout').get('relative-paths', 'false'))
        return relative_paths in [True, 'true']

    def set_executable_path(self):
        if not is_windows:
            return
        if not self.is_relative_paths_option_set():
            python_executable = self.buildout.get('buildout').get('executable')
            self.options['executable'] = python_executable


class Scripts(zc.recipe.egg.Scripts, AbsoluteExecutablePathMixin, LazyImportMixin):
    def install(self):
        func = super(Scripts, self).install
        self.set_executable_path()
        return Workaround(self, gui=False)(func)()

    update = install


@contextmanager
def patch_get_entry_map_for_gui_scripts():
    from pkg_resources import get_entry_map as _get_entry_map
    def get_entry_map(dist, group=None):
        return _get_entry_map(dist, "gui_scripts")
    import pkg_resources
    pkg_resources.get_entry_map = get_entry_map
    try:
        yield
    finally:
        pkg_resources.get_entry_map = _get_entry_map


@contextmanager
def patch_get_entry_info_for_gui_scripts():
    def get_entry_info(self, group, name):
        return self.get_entry_map("gui_scripts" if group == "console_scripts" else group).get(name)
    with mock.patch("pkg_resources.Distribution.get_entry_info", new=get_entry_info):
        yield


class GuiScripts(zc.recipe.egg.Scripts, AbsoluteExecutablePathMixin, LazyImportMixin):
    def install(self):
        with patch_get_entry_map_for_gui_scripts():
            with patch_get_entry_info_for_gui_scripts():
                func = super(GuiScripts, self).install
                self.set_executable_path()
                return Workaround(self, gui=True)(func)()

    update = install


# used as entry point to gui-script-test
def nothing():
    pass
