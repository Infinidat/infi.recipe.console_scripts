__import__("pkg_resources").declare_namespace(__name__)

import zc.recipe.egg
import mock
from infi.pyutils.contexts import contextmanager
from .lazy_imports import LazyImportsWorkaround, LazyImportMixin
from .windows import WindowsWorkaround, is_windows


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
        self.set_executable_path()
        installed_files = super(Scripts, self).install()
        WindowsWorkaround.apply(self, False, installed_files)
        LazyImportsWorkaround.apply(self, installed_files)
        return installed_files

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
                self.set_executable_path()
                installed_files = super(GuiScripts, self).install()
                WindowsWorkaround.apply(self, True, installed_files)
                LazyImportsWorkaround.apply(self, installed_files)
                return installed_files

    update = install


# used as entry point to gui-script-test
def nothing():
    pass
