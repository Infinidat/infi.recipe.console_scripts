Overview
========

This is a buildout recipe that extends `zc.recipe.egg`, by adding the following features:

* write application manifests when running on Windows
* support for adding a smaller set of python packages to `sys.path`, so calling `<executable> --help` will load faster


Checking out the code
=====================

Run the following:

    easy_install -U infi.projector
    projector devenv build
