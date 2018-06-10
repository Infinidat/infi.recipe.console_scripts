Overview
========

This is a buildout recipe that extends `zc.recipe.egg`, by adding the following features:

* write application manifests when running on Windows
* support for adding a smaller set of python packages to `sys.path`, so calling `<executable> --help` will load faster


Checking out the code
=====================

To check out the code for development purposes, clone the git repository and run the following commands:

    easy_install -U infi.projector
    projector devenv build

Python 3
========
Python 3 support is experimental and untested at this stage.
