import os
is_windows = os.name == 'nt'

VIRTUALENV_SECTION = """{shebang}
import os
{code_before}
# When working inside a virtual environment, IPython tries to load all of the venv Python packages:
os.environ.pop('VIRTUAL_ENV', None)
{code_after}
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
        import_line = 0
        content_lines = content.split("\n")
        for import_line, line in enumerate(reversed(content_lines)):
            if "import" in line:
                # we take the last line with "import" in it, it is the import of the entry point
                break
        import_line = len(content_lines) - import_line
        shebang = content_lines[0]
        code_before = '\n'.join(content_lines[1:import_line - 1])
        code_after = '\n'.join(content_lines[import_line - 1:])

        template_kwargs = dict(shebang=shebang,
                               import_line=import_line,
                               code_before=code_before,
                               code_after=code_after)
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
