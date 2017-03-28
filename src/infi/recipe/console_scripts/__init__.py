__import__("pkg_resources").declare_namespace(__name__)

from contextlib import contextmanager
from .minimal_packages import MinimalPackagesWorkaround, MinimalPackagesMixin
from .windows import WindowsWorkaround, is_windows
from .virtualenv import VirtualenvWorkaround
from .egg import Scripts


class AbsoluteExecutablePathMixin(object):
    def is_relative_paths_option_set(self):
        relative_paths = self.options.get('relative-paths',
                                          self.buildout.get('buildout').get('relative-paths', 'false'))
        return relative_paths in [True, 'true']

    def set_executable_path(self):
        if is_windows and not self.is_relative_paths_option_set():
            python_executable = self.buildout.get('buildout').get('executable')
            self.options['executable'] = python_executable


class Scripts(Scripts, AbsoluteExecutablePathMixin, MinimalPackagesMixin):
    def install(self):
        self.set_executable_path()
        installed_files = super(Scripts, self).install()
        WindowsWorkaround.apply(self, False, installed_files)
        MinimalPackagesWorkaround.apply(self, installed_files)
        VirtualenvWorkaround.apply(self, installed_files)
        return installed_files

    update = install


@contextmanager
def patch(parent, name, value):
    previous = getattr(parent, name, None)
    setattr(parent, name, value)
    try:
        yield
    finally:
        setattr(parent, name, previous)


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


class GuiScripts(Scripts, AbsoluteExecutablePathMixin, MinimalPackagesMixin):
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


def patch_buildout_wheel():
    import buildout.wheel
    import glob
    WheelInstaller = buildout.wheel.WheelInstaller

    def wrapper(func):
        def wrapper(basename):
            return WheelInstaller((glob.glob('{}*'.format(basename)) + [basename])[0])
        return wrapper

    buildout.wheel.WheelInstaller = wrapper(buildout.wheel.WheelInstaller)


def _get_matching_dist_in_location(dist, location):
    """
    Check if `locations` contain only the one intended dist.
    Return the dist with metadata in the new location.
    """
    # Getting the dist from the environment causes the
    # distribution meta data to be read.  Cloning isn't
    # good enough.
    import pkg_resources
    env = pkg_resources.Environment([location])
    dists = [ d for project_name in env for d in env[project_name] ]
    dist_infos = [ (d.project_name, d.version) for d in dists ]
    if dist_infos == [(dist.project_name, dist.version)]:
        return dists.pop()
    if dist_infos == [(dist.project_name.lower(), dist.version)]:
        return dists.pop()

def patch_zc_buildout_easy_install():
    import zc.buildout.easy_install
    zc.buildout.easy_install._get_matching_dist_in_location = _get_matching_dist_in_location

# buildout.wheel on Windows is having problems installing non-lower-case wheels
try:
    patch_buildout_wheel()
except ImportError:
    pass

patch_zc_buildout_easy_install()
