import os
is_windows = os.name == 'nt'


# The lazy import section tries to run the entry point with as little packages as possible in sys.path.
# Only if this will fail (with ImportError, as there will be missing packages), it will continue with a normal run
LAZY_IMPORT_SECTION_TEMPLATE = """
sys.path[0:0] = [
{sys_path_lines}
  ]

if __name__ == '__main__':
  try:
    {import_line}
{sys_exit_line}
  except ImportError:
    pass

"""


def get_python_script_filter(bin_dirpath):
    # we want to get only the python script files under the <buildout>/<bin> directory

    def func(filepath):
        if not filepath.startswith(bin_dirpath):
            return False
        if is_windows:
            return not filepath.endswith("-script.py")
        return True  # we just want to save us the trouble of reading windows binary files
    return func


class LazyImportMixin(object):
    def get_lazy_import_dict(self):
        # format of each item in lazy-imports should be:
        #   script_name:package1,package2,package3
        option = self.options.get("lazy-imports",
                                  self.buildout.get("development-scripts").get("lazy-imports", ""))
        result = dict()
        for item in option.split():
            if ":" not in item:
                continue
            script_name, minimal_packages = item.split(":")
            minimal_packages = minimal_packages.split(",")
            result[script_name] = minimal_packages
        return result

    def get_python_script_filter(self):
        return get_python_script_filter(self.options.get("bin-directory"))


class LazyImportsWorkaroundMixin(object):
    def __init__(self, recipe):
        self._lazy_import_dict = recipe.get_lazy_import_dict()
        self._python_script_filter = recipe.get_python_script_filter()

    def _generate_lazy_import_section(self, content, lazy_imports):
        sys_path_lines = []
        import_line = ""
        sys_exit_line = "raise ImportError"
        for line in content.split("\n"):
            if "import" in line:
                # we take the last line with "import" in it, it is the import of the entry point
                import_line = line
            if "sys.exit" in line:
                # this is the line that runs the entry point
                sys_exit_line = line
            if line.startswith("  join") and any(lazy_import in line for lazy_import in lazy_imports):
                sys_path_lines.append(line)
        sys_path_lines = "\n".join(sys_path_lines)
        template_kwargs = dict(sys_path_lines=sys_path_lines, import_line=import_line, sys_exit_line=sys_exit_line)
        return LAZY_IMPORT_SECTION_TEMPLATE.format(**template_kwargs)

    def _add_lazy_import_section(self, filepath, lazy_imports):
        if is_windows and not filepath.endswith(".py"):
            return
        with open(filepath) as fd:
            content = fd.read()
        section = self._generate_lazy_import_section(content, lazy_imports)
        content = content.replace("import sys\n", "import sys\n" + section)
        with open(filepath, 'w') as fd:
            fd.write(content)

    def _apply_lazy_imports(self, installed_files):
        if not self._lazy_import_dict:
            return
        for filepath in filter(self._python_script_filter, installed_files):
            # the keys in lazy_import_dict are script names
            # the value is a list of minimal packages to try for the script specified by the key
            # so if any installed file matches a key, add the lazy import section with that list of packages
            for key, value in self._lazy_import_dict.items():
                if key in filepath:
                    self._add_lazy_import_section(filepath, value)
