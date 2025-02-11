import argparse
import json
import os.path
import platform
import subprocess
import sys

from packaging.version import Version


RETURN_CODES = {
    "SETUP_DIR_INVALID": 1,
    "PROVENANCE_FILE_INVALID": 2,
    "DEFAULT_PYTHON_NOT_SET": 3,
    "PLATFORM_MISMATCH": 4,
    "GIT_EXECUTABLE_NOT_FOUND": 5,
    "VIRTUALENV_SETUP_FAILED": 6,
    "REQUIREMENTS_INSTALL_FAILED": 7,
    "PLUGIN_CLONE_FAILED": 8,
    "GIT_SWITCH_FAILED": 9,
    "MAPCLIENT_USE_FAILED": 10,
}


def _description_text():
    return_codes = ';'.join(' {} - {}'.format(val, key) for key, val in RETURN_CODES.items())
    return f"""
    Setup a MAP Client environment exactly as recorded in a provenance information file.
    
    Return codes:
    {return_codes}
    """


def _parse_args():
    parser = argparse.ArgumentParser(prog="setup_from_provenance", description=_description_text())
    parser.add_argument("setup_dir", help="directory to setup MAP Client in, must exist.")
    parser.add_argument("-p", "--provenance-file", help="specify the provenance file.", default="provenance.json")

    return parser.parse_args()


def _which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, permissions):
        return (os.path.exists(fn) and os.access(fn, permissions)
                and not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly rather
    # than referring to PATH directories. This includes checking relative to the
    # current directory, e.g. ./script
    if os.path.dirname(cmd):
        if sys.platform == "win32":
            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            files = [cmd]
        for name in files:
            if _access_check(name, mode):
                return name

        return None

    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if not os.curdir in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        # If it does match, only test that one, otherwise we have to try
        # others.
        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for directory in path:
        normdir = os.path.normcase(directory)
        if not normdir in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(directory, thefile)
                if _access_check(name, mode):
                    return name

    return None


def _is_map_client_provenance_file(provenance_file):
    if not os.path.isfile(provenance_file):
        return False

    with open(provenance_file) as fh:
        content = json.load(fh)

    return "id" in content and content["id"] == "map-client-provenance-record-report" and "version" in content


def _map_client_requirements(info):
    return [f"mapclient == {info['version']}"]


def _package_requirements(info):
    r = []
    for package, package_data in info.items():
        r.append(f"{package} == {package_data['version']}")
        if package_data['location'] != "PyPI":
            print(f"Package: {package} is not installed from PyPI!")

    return r


def _plugin_requirements(info):
    return info


def _get_exe_part(base_dir, name, app_name):
    common_part = os.path.commonpath([sys.executable, sys.prefix])
    end_part = sys.executable.replace(common_part + os.path.sep, "")
    exe_part = end_part.replace("python", app_name, 1)

    return os.path.join(base_dir, name, exe_part)


def _get_virtual_environment_pip(base_dir, name):
    return _get_exe_part(base_dir, name, "pip")


def _get_virtual_environment_map_client_use(base_dir, name):
    return _get_exe_part(base_dir, name, "mapclient_use")


def _platform_match(info):
    return Version(platform.python_version()) == Version(info["version"]) and info["platform"] == sys.platform


def main():
    venv_directory_name = "venv_map_client"
    args = _parse_args()

    if not os.path.isdir(args.setup_dir):
        return RETURN_CODES["SETUP_DIR_INVALID"]

    if not _is_map_client_provenance_file(args.provenance_file):
        return RETURN_CODES["PROVENANCE_FILE_INVALID"]

    with open(args.provenance_file) as fh:
        content = json.load(fh)

    software_info = content["software_info"]
    if Version(content["version"]) == Version("0.1.0"):
        if sys.platform == "darwin":
            python_info = {"version": "3.11.11", "platform": "darwin"}
        else:
            print(f"Default Python information not set for this platform ({sys.platform}).")
            return RETURN_CODES["DEFAULT_PYTHON_NOT_SET"]
    else:
        python_info = software_info["python"]

    if not _platform_match(python_info):
        print(f"Script requires platform {python_info['platform']} at version {python_info['version']}, "
              f"the current system has been detected as {sys.platform} at version {platform.python_version()} which is not suitable.")
        return RETURN_CODES["PLATFORM_MISMATCH"]

    git_exe = _which("git")
    if git_exe is None:
        return RETURN_CODES["GIT_EXECUTABLE_NOT_FOUND"]

    map_client_requirement = _map_client_requirements(software_info["mapclient"])
    package_requirements = _package_requirements(software_info["packages"])
    requirements = map_client_requirement + package_requirements

    plugin_requirements = _plugin_requirements(software_info["plugins"])

    result = subprocess.run([sys.executable, "-m", "venv", venv_directory_name], cwd=args.setup_dir)
    if result.returncode != 0:
        return RETURN_CODES["VIRTUALENV_SETUP_FAILED"]

    with open(os.path.join(args.setup_dir, "requirements.txt"), "w") as fh:
        fh.write("\n".join(requirements))

    virtual_environment_pip_exe = _get_virtual_environment_pip(args.setup_dir, venv_directory_name)

    result = subprocess.run([virtual_environment_pip_exe, "install", "-r", "requirements.txt"], cwd=args.setup_dir, capture_output=True)
    if result.returncode != 0:
        return RETURN_CODES["REQUIREMENTS_INSTALL_FAILED"]

    plugin_dir = os.path.join(args.setup_dir, "plugins")
    os.makedirs(plugin_dir, exist_ok=True)

    for p, p_data in plugin_requirements.items():
        if os.path.exists(os.path.join(plugin_dir, p)):
            result = subprocess.run(["echo", os.path.join(plugin_dir, p)])
        else:
            result = subprocess.run([git_exe, "clone", "--depth",  "1", "--branch", f"v{p_data['version']}", p_data["location"], p], cwd=plugin_dir, capture_output=True)

        if result.returncode != 0:
            print(f"Failed to clone: {p} @ v{p_data['version']}.")
            return RETURN_CODES["PLUGIN_CLONE_FAILED"]

        result = subprocess.run([git_exe, "switch", "-c", f"v{p_data['version']}"], cwd=os.path.join(plugin_dir, p), capture_output=True)
        if result.returncode != 0 and result.stderr.decode() != f"fatal: a branch named 'v{p_data['version']}' already exists\n":
            print(f"Failed to switch branch to v{p_data['version']}.")
            return RETURN_CODES["GIT_SWITCH_FAILED"]

    # Temporary!!! Take the following line out.
    subprocess.run([virtual_environment_pip_exe, "install", "-e", "/Users/hsor001/Projects/musculoskeletal/mapclient/src"], capture_output=True)

    map_client_use_exe = _get_virtual_environment_map_client_use(args.setup_dir, venv_directory_name)
    result = subprocess.run([map_client_use_exe, args.setup_dir, "-d", plugin_dir])
    if result.returncode != 0:
        return RETURN_CODES["MAPCLIENT_USE_FAILED"]

    return 0


if __name__ == "__main__":
    sys.exit(main())
