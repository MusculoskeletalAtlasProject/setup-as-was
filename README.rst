Setup MAP Client from Provenance
================================

This repository contains a script to setup a MAP Client environment from provenance data.

Usage
-----

setup_from_provenance [-h] [-p PROVENANCE_FILE] setup_dir

Setup a MAP Client environment exactly as recorded in a provenance information file.

Return codes:
    1 - SETUP_DIR_INVALID;
    2 - PROVENANCE_FILE_INVALID;
    3 - DEFAULT_PYTHON_NOT_SET;
    4 - PLATFORM_MISMATCH;
    5 - GIT_EXECUTABLE_NOT_FOUND;
    6 - VIRTUALENV_SETUP_FAILED;
    7 - REQUIREMENTS_INSTALL_FAILED;
    8 - PLUGIN_CLONE_FAILED;
    9 - GIT_SWITCH_FAILED;
    10 - MAPCLIENT_USE_FAILED

positional arguments:
  setup_dir             directory to setup MAP Client in, must exist.

options:
  -h, --help            show this help message and exit
  -p PROVENANCE_FILE, --provenance-file PROVENANCE_FILE
                        specify the provenance file.

command::

  python src/setup_map_client_from_provenance.py -p <path-to-provenance-file> <setup-dir>

where <path-to-provenance-file> is an absolute path to a provenance information file and <setup-dir> is an absolute path to an existing directory.
