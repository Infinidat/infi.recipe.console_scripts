import os
is_windows = os.name == 'nt'


# The minimal packages section tries to run the entry point with as little packages as possible in sys.path.
# Only if this will fail (with ImportError, as there will be missing packages), it will continue with a normal run
MINIMAL_PACKAGES_SECTION_TEMPLATE = """
import pkg_resources

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
            return filepath.endswith("-script.py")
        return True  # we just want to save us the trouble of reading windows binary files
    return func


class MinimalPackagesMixin(object):
    def get_minimal_packages_dict(self):
        # format of each item in minimal-packages should be:
        #   script_name:package1,package2,package3
        option = self.options.get("minimal-packages", "")
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


class MinimalPackagesWorkaround(object):
    @classmethod
    def _generate_minimal_packages_section(cls, content, minimal_packages):
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
            if (line.startswith("  join") or line.startswith("  '")) \
               and any(minimal_package in line for minimal_package in minimal_packages):
                sys_path_lines.append(line)
        sys_path_lines = "\n".join(sys_path_lines)
        template_kwargs = dict(sys_path_lines=sys_path_lines, import_line=import_line, sys_exit_line=sys_exit_line)
        return MINIMAL_PACKAGES_SECTION_TEMPLATE.format(**template_kwargs)

    @classmethod
    def _add_minimal_packages_section(cls, filepath, minimal_packages):
        if is_windows and not filepath.endswith(".py"):
            return
        with open(filepath) as fd:
            content = fd.read()
        section = cls._generate_minimal_packages_section(content, minimal_packages)
        content = content.replace("if __name__ == '__main__':\n", "reload(pkg_resources)\nif __name__ == '__main__':\n")
        content = content.replace("import sys\n", "import sys\n" + section)
        with open(filepath, 'w') as fd:
            fd.write(content)

    @classmethod
    def apply(cls, recipe, installed_files):
        minimal_packages_dict = recipe.get_minimal_packages_dict()
        python_script_filter = recipe.get_python_script_filter()
        if not minimal_packages_dict:
            return
        for filepath in filter(python_script_filter, installed_files):
            # the keys in minimal_packages_dict are script names
            # the value is a list of minimal packages to try for the script specified by the key
            # so if any installed file matches a key, add the minimal packages section with that list of packages
            for key, value in minimal_packages_dict.items():
                if key in filepath:
                    cls._add_minimal_packages_section(filepath, value)
