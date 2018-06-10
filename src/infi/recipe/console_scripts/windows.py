from pkg_resources import resource_stream, resource_filename
import shutil

import sys
import os
is_windows = os.name == 'nt'
is_64 = sys.maxsize > 2**32
arch = 'x64' if is_64 else 'x86'


try:
    embedded_launcher = resource_stream(__name__, 'embed-{}.exe'.format(arch)).read()
    embedded_gui_launcher = resource_stream(__name__, 'embed-gui-{}.exe'.format(arch)).read()
except IOError:
    # https://bitbucket.org/pypa/setuptools/issue/1/disable-installation-of-windows-specific
    pass

MICROSOFT_VC90_CRT = {
    'Microsoft.VC90.CRT.manifest': resource_filename(__name__, "Microsoft.VC90.CRT.manifest-{}".format(arch)),
    'msvcm90.dll': resource_filename(__name__, "msvcm90.dll-{}".format(arch)),
    'msvcp90.dll': resource_filename(__name__, "msvcp90.dll-{}".format(arch)),
    'msvcr90.dll': resource_filename(__name__, "msvcr90.dll-{}".format(arch))
}

MANIFEST = \
"""
<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<assembly xmlns='urn:schemas-microsoft-com:asm.v1' manifestVersion='1.0'>
  {uac}
  {vc90}
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10 -->
      <supportedOS Id="{{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}}"/>
      <!-- Windows 8.1 -->
      <supportedOS Id="{{1f676c76-80e1-4239-95bb-83d0f6d0da78}}"/>
      <!-- Windows Vista -->
      <supportedOS Id="{{e2011457-1546-43c5-a5fe-008deee3d3f0}}"/>
      <!-- Windows 7 -->
      <supportedOS Id="{{35138b9a-5d96-4fbd-8e2d-a2440225f93a}}"/>
      <!-- Windows 8 -->
      <supportedOS Id="{{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}}"/>
    </application>
  </compatibility>
</assembly>
"""

MANIFEST_UAC = \
"""
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
"""

MANIFEST_VC90 = \
"""
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type='win32' name='Microsoft.VC90.CRT' version='9.0.21022.8' processorArchitecture='{}' publicKeyToken='1fc8b3b9a1e18e3b' />
    </dependentAssembly>
  </dependency>
""".format('amd64' if is_64 else 'x86')


def executable_filter(filepath):
    return filepath.endswith('exe') and 'buildout' not in filepath


class WindowsWorkaround(object):
    @classmethod
    def _replace_launcher(cls, filepath, gui=False):
        with open(filepath, 'wb') as fd:
            fd.write(embedded_gui_launcher if gui else embedded_launcher)

    @classmethod
    def _write_manifest(cls, filepath, with_vc90=True, with_uac=True):
        with open(filepath, 'w') as fd:
            fd.write(MANIFEST.format(uac=MANIFEST_UAC if with_uac else '',
                                     vc90=MANIFEST_VC90 if with_vc90 else ''))

    @classmethod
    def _write_vc90_crt_private_assembly(cls, dirpath):
        assembly_basedir = os.path.join(dirpath, 'Microsoft.VC90.CRT')
        if not os.path.exists(assembly_basedir):
            os.makedirs(assembly_basedir)
        for filename, src in MICROSOFT_VC90_CRT.items():
            dst = os.path.join(assembly_basedir, filename)
            if not os.path.exists(dst):
                shutil.copy(src, dst)

    @classmethod
    def apply(cls, recipe, gui, installed_files):
        require_administrative_privileges = recipe.options.get('require-administrative-privileges', 'false')
        with_uac = require_administrative_privileges in (True, "true")
        if not is_windows:
            return
        for filepath in filter(executable_filter, installed_files):
            cls._replace_launcher(filepath, gui)
            cls._write_manifest('{}.manifest'.format(filepath), with_uac=with_uac)
            cls._write_vc90_crt_private_assembly(os.path.dirname(filepath))


class CommandlineWorkaround(object):
    def __init__(self, admin_required):
        super(CommandlineWorkaround, self).__init__()
        self.options = {"require-administrative-privileges": admin_required}


def _replace_script(gui):
    if not is_windows:
        return
    [_, filename, admin_required] = sys.argv
    filename = filename if filename.endswith(".exe") else filename + ".exe"
    basename = os.path.basename(filename)
    files = [filename, basename]
    files.extend([os.path.join(dirname, basename) for dirname in os.environ.get("PATH", "").split(os.pathsep)])
    files = [item for item in files if os.path.exists(item)]
    WindowsWorkaround.apply(CommandlineWorkaround(admin_required in ("1", "True", "true")), gui, files[:1])


def replace_console_script():
  _replace_script(False)


def replace_gui_script():
  _replace_script(True)
