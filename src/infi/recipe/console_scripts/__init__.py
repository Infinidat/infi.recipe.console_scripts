__import__("pkg_resources").declare_namespace(__name__)

import zc.recipe.egg
from infi.pyutils.contexts import contextmanager
from infi.pyutils.patch import patch
from .minimal_packages import MinimalPackagesWorkaround, MinimalPackagesMixin
from .windows import WindowsWorkaround, is_windows
from .virtualenv import VirtualenvWorkaround


class AbsoluteExecutablePathMixin(object):
    def is_relative_paths_option_set(self):
        relative_paths = self.options.get('relative-paths',
                                          self.buildout.get('buildout').get('relative-paths', 'false'))
        return relative_paths in [True, 'true']

    def set_executable_path(self):
        if is_windows and not self.is_relative_paths_option_set():
            python_executable = self.buildout.get('buildout').get('executable')
            self.options['executable'] = python_executable


class Scripts(zc.recipe.egg.Scripts, AbsoluteExecutablePathMixin, MinimalPackagesMixin):
    def install(self):
        self.set_executable_path()
        installed_files = super(Scripts, self).install()
        WindowsWorkaround.apply(self, False, installed_files)
        MinimalPackagesWorkaround.apply(self, installed_files)
        VirtualenvWorkaround.apply(self, installed_files)
        return installed_files

    update = install


@contextmanager
def patch_get_entry_map_for_gui_scripts():
    import pkg_resources
    _get_entry_map = pkg_resources.get_entry_map

    def get_entry_map(dist, group=None):
        return _get_entry_map(dist, "gui_scripts")

    with patch(pkg_resources, "get_entry_map", get_entry_map):
        yield


@contextmanager
def patch_get_entry_info_for_gui_scripts():
    import pkg_resources

    def get_entry_info(self, group, name):
        return self.get_entry_map("gui_scripts" if group == "console_scripts" else group).get(name)

    with patch(pkg_resources.Distribution, "get_entry_info", get_entry_info):
        yield


class GuiScripts(zc.recipe.egg.Scripts, AbsoluteExecutablePathMixin, MinimalPackagesMixin):
    def install(self):
        with patch_get_entry_map_for_gui_scripts():
            with patch_get_entry_info_for_gui_scripts():
                self.set_executable_path()
                installed_files = super(GuiScripts, self).install()
                WindowsWorkaround.apply(self, True, installed_files)
                MinimalPackagesWorkaround.apply(self, installed_files)
                return installed_files

    update = install


# used as entry point to gui-script-test
def nothing():
    pass
