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


class WindowsWorkaroundMixin(object):
    def __init__(self, recipe, gui=False):
        super(WindowsWorkaroundMixin, self).__init__()
        self._require_administrative_privileges = recipe.options.get('require-administrative-privileges', True)
        self._gui = gui

    def _replace_launcher(self, filepath, gui=False):
        with open(filepath, 'wb') as fd:
            fd.write(embedded_gui_launcher if gui else embedded_launcher)

    def _write_manifest(self, filepath, with_vc90=True, with_uac=True):
        with open(filepath, 'w') as fd:
            fd.write(MANIFEST.format(uac=MANIFEST_UAC if with_uac else '',
                                     vc90=MANIFEST_VC90 if with_vc90 else ''))

    def _write_vc90_crt_private_assembly(self, dirpath):
        assembly_basedir = os.path.join(dirpath, 'Microsoft.VC90.CRT')
        if not os.path.exists(assembly_basedir):
            os.makedirs(assembly_basedir)
        for filename, src in MICROSOFT_VC90_CRT.items():
            dst = os.path.join(assembly_basedir, filename)
            if not os.path.exists(dst):
                shutil.copy(src, dst)

    def _apply_windows_workarounds(self, installed_files):
        if not is_windows:
            return
        for filepath in filter(executable_filter, installed_files):
            self._replace_launcher(filepath, self._gui)
            self._write_manifest('{}.manifest'.format(filepath), with_uac=self._require_administrative_privileges)
            self._write_vc90_crt_private_assembly(os.path.dirname(filepath))
