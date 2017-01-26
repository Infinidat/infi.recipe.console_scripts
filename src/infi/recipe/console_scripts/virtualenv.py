import os
is_windows = os.name == 'nt'

VIRTUALENV_SECTION = """{shebang}
import os
# When working inside a virtual environment, IPython tries to load all of the venv Python packages:
os.environ.pop('VIRTUAL_ENV', None)
{code}
"""


def get_python_script_filter(bin_dirpath):
    # we want to get only the python script files under the <buildout>/<bin> directory

    def func(filepath):
        if not filepath.startswith(bin_dirpath):
            return False
        if is_windows:
            return filepath.endswith("-script.py")
        return True  # we just want to save us the trouble of reading windows binary files
    return func


class VirtualenvWorkaround(object):
    @classmethod
    def _generate_virtualenv_content(cls, content):
        content_lines = content.split('\n')
        shebang = content_lines[0]
        code = '\n'.join(content_lines[1:])
        template_kwargs = dict(shebang=shebang, code=code)
        return VIRTUALENV_SECTION.format(**template_kwargs)

    @classmethod
    def _add_virtualenv_section(cls, filepath):
        with open(filepath) as fd:
            content = fd.read()
        new_content = cls._generate_virtualenv_content(content)
        with open(filepath, 'w') as fd:
            fd.write(new_content)

    @classmethod
    def apply(cls, recipe, installed_files):
        python_script_filter = recipe.get_python_script_filter()
        for filepath in filter(python_script_filter, installed_files):
            # the keys in minimal_packages_dict are script names
            # the value is a list of minimal packages to try for the script specified by the key
            # so if any installed file matches a key, add the minimal packages section with that list of packages
            cls._add_virtualenv_section(filepath)
