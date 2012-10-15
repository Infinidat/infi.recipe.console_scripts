__import__("pkg_resources").declare_namespace(__name__)

import os
import zc.recipe.egg
import sys
import os
import shutil
from infi.pyutils.decorators import wraps
from pkg_resources import resource_stream, resource_filename

is_64 = sys.maxsize > 2**32
arch = 'x64' if is_64 else 'x86'
distribute_launcher = resource_stream('setuptools', 'cli-{}.exe'.format('64' if is_64 else '32')).read()
embedded_launcher = resource_stream(__name__, 'embed-{}.exe'.format(arch)).read()


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

def is_distribute_launcher(filepath):
    with open(filepath, 'rb') as fd:
        return fd.read() == distribute_launcher

def is_buildout_launcher(filepath):
    return filepath.endswith('buildout.exe')

def replace_launcher(filepath):
    with open(filepath, 'wb') as fd:
        fd.write(embedded_launcher)

def write_manifest(filepath, with_vc90=True, with_uac=True):
    with open(filepath, 'w') as fd:
        fd.write(MANIFEST.format(uac=MANIFEST_UAC if with_uac else '',
                                 vc90=MANIFEST_VC90 if with_vc90 else ''))

def executable_filter(filepath):
    return filepath.endswith('exe') and 'buildout' not in filepath

def write_vc90_crt_private_assembly(dirpath):
    assembly_basedir = os.path.join(dirpath, 'Microsoft.VC90.CRT')
    if not os.path.exists(assembly_basedir):
        os.makedirs(assembly_basedir)
    for filename, src in MICROSOFT_VC90_CRT.items():
        dst = os.path.join(assembly_basedir, filename)
        if not os.path.exists(dst):
            shutil.copy(src, dst)

class Workaround(object):
    def __init__(self, require_administrative_privileges=True):
        self._require_administrative_privileges = require_administrative_privileges

    def __call__(self, func):
        @wraps(func)
        def callee(*args, **kwargs):
            installed_files = func(*args, **kwargs)
            for filepath in filter(executable_filter, installed_files):
                replace_launcher(filepath)
                write_manifest('{}.manifest'.format(filepath), with_uac=self._require_administrative_privileges)
                write_vc90_crt_private_assembly(os.path.dirname(filepath))
            return installed_files
        return callee

def workaround(func):
    return Workaround()(func)

class AbsoluteExecutablePathMixin(object):
    def is_relative_paths_option_set(self):
        relative_paths = self.options.get('relative-paths', self.buildout.get('buildout').get('relative-paths', 'false'))
        return relative_paths in [True, 'true']

    def set_executable_path(self):
        from os import path, curdir
        if not self.is_relative_paths_option_set():
            buildout_directory = self.buildout.get('buildout').get('buildout-directory', curdir)
            self.options['executable'] = path.abspath(path.join(buildout_directory, self.options.get('executable')))

class Scripts(zc.recipe.egg.Scripts, AbsoluteExecutablePathMixin):
    def install(self):
        func = super(Scripts, self).install
        require = self.options.get('require-administrative-privileges', True)
        self.set_executable_path()
        return Workaround(require)(func)()

    update = install

