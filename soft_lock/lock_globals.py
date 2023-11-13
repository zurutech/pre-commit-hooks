import distutils.spawn
import glob
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterator, List

USE_HTTPS = True
HOST = "api.zuru-soft-lock.dreamcatcher.zuru.link"
PORT = 443

# changed via CLI
verbose = False

# Will contains the content of "~/.zuru-soft-lock/user-data"
g_user_data: object = None

all_files = [
    "cli_utils.py",
    "git-history",
    "git-lock",
    "git-locks",
    "git-unlock",
    "run_python",
]


class NotAuthorizedError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def print_verbose(msg):
    if verbose:
        print("# " + msg)


def make_post(authorization, path, body, return_error=False) -> dict:
    """
    Perform an api request to the backend
    :param authorization: A string retrieved with find_authorization
    :param path: A path to invoke (eg: '/get-locks')
    :param body: The request body
    :param return_error: If true, return the error instead of exiting
    :return: The response from the server
    :raises: NotAuthorizedError: In case of error 401
    """
    try:
        print_verbose(f"requesting {path}")
        data = json.dumps(body)
        headers = {
            "Content-type": "application/json",
            "Authorization": authorization,
        }
        connection = (
            http.client.HTTPSConnection(HOST, PORT, timeout=20)
            if USE_HTTPS
            else http.client.HTTPConnection(HOST, PORT, timeout=20)
        )
        connection.request("POST", path, data, headers)
        response = connection.getresponse()
        response_body = response.read().decode()
        if response.status != 200 and response.status != 400:
            if response.status == 401:
                raise NotAuthorizedError("Not authorized")
            print(
                "ERROR: Server replied with {} {}".format(
                    response.status, response_body
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        response_json = json.loads(response_body)
        if isinstance(response_json.get("error"), str):
            if return_error:
                return response_json
            print(response_json.get("error"), file=sys.stderr)
            sys.exit(1)
        return response_json
    except ConnectionRefusedError as err:
        print(f"ERROR: Connection refused {HOST}:{PORT}: {err}", file=sys.stderr)
        sys.exit(1)


def get_actual_filename(name: str) -> str:
    """
    Find a file with the right cases (for case-insensitive file systems)
    If the file doesn't exists, return the string as is
    """
    result = glob.glob(f"{name[:-1]}[{name[-1]}]")
    return result[0] if len(result) > 0 else name


def get_clean_paths(paths, verify_presence: bool) -> Iterator[Path]:
    """
    Returns a list of paths that are relative to the git root
    Note: if the path is a directory, it will be ignored
    """
    git_root = get_git_root()

    for path in paths:
        path = Path(path).resolve()

        if not os.path.isfile(path):
            # find a name relative to the git root
            joined = git_root / path
            if joined.is_file():
                path = joined

        if path.is_dir():
            # Ignore directories
            continue

        if verify_presence:
            if not os.path.isfile(path):
                print(f"ERROR: Cannot find file '{path}'", file=sys.stderr)
                sys.exit(1)

            # On windows, the file may be in the wrong case
            if os.name == "nt":
                path = get_actual_filename(str(path))

        yield Path(path)


def get_repository_path(path, repo):
    """Returns the path relative to the repository"""

    relative_path = to_system_independent_path(os.path.relpath(path, repo))
    if relative_path.startswith("../"):
        print("ERROR: File outside repository", file=sys.stderr)
        sys.exit(1)

    return relative_path


def get_git_root() -> Path:
    return Path(spawn(["git", "rev-parse", "--show-toplevel"]).strip()).resolve()


def get_git_root_from_dir(path) -> Path:
    """
    Retrieve the git repository to which path belongs
    :param path the path of a file or a directory
    """

    directory = Path(path)
    while not directory.is_dir():
        directory = directory.parent

    git_root = spawn(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"]
    ).strip()
    return Path(git_root).resolve()


def find_ssh():
    ssh = os.getenv("GIT_SSH")
    if isinstance(ssh, str):
        return ssh

    from_path = distutils.spawn.find_executable("ssh")
    if isinstance(from_path, str):
        print_verbose(f"ssh found: {from_path}")
        return from_path

    print("ERROR: ssh not found", file=sys.stderr)
    sys.exit(1)


def find_lfs_root(git_root=Path.cwd()):
    url = spawn(["git", "-C", str(git_root), "remote", "get-url", "origin"]).strip()
    if url.startswith("https://"):
        parsed = urllib.parse.urlparse(url)
        return parsed.path.lstrip("/")
    split = url.split("git@gitlab.com:")
    if len(split) == 2 and split[0] == "":
        print_verbose("found root " + split[1])
        return split[1]
    print(f"ERROR: File not found '{url}'", file=sys.stderr)
    sys.exit(1)


def get_full_name():
    name = spawn(["git", "config", "user.name"]).strip()
    if not name:
        print("ERROR: user.name not found in directory", file=sys.stderr)
        sys.exit(1)
    print_verbose("found user.name: " + name)
    return name


def find_authorization(repo_path) -> str:
    """Returns the authorization to use to communicate with the backend"""
    global g_user_data

    # load cached zsl token
    home = get_app_home()
    home.mkdir(parents=True, exist_ok=True)

    user_data_path = home / "user-data"
    print_verbose(f"Loading {user_data_path}")
    if user_data_path.exists():
        with open(user_data_path) as f:
            user_data = json.load(f)

        zsl_authorization = _validate_and_get_authorization(user_data)
        if zsl_authorization is not None:
            g_user_data = user_data
            return zsl_authorization

    lfs_authorization = _generate_lfs_authorization(repo_path)
    user_data = make_post(lfs_authorization, "/authenticate", {})
    g_user_data = user_data

    with open(user_data_path, "w") as f:
        json.dump(user_data, f, indent=2)

    return lfs_authorization


def get_gitlab_username() -> str:
    assert (
        g_user_data is not None
    ), "get_gitlab_username() can only be called after find_authorization()"
    assert isinstance(g_user_data["gitlab-username"], str)

    return g_user_data["gitlab-username"]


def _generate_lfs_authorization(repo_path):
    ssh = find_ssh()
    print_verbose("generating GitLab token")
    json_auth = spawn(
        [ssh, "git@gitlab.com", "git-lfs-authenticate", str(repo_path), "upload"]
    ).strip()
    print_verbose("token generated")
    return json.loads(json_auth).get("header").get("Authorization")


def to_system_independent_path(path: str):
    return path.replace("\\", "/")


def spawn(args: List, stdin=""):
    def _spawn_error(exit_code):
        print(f"ERROR: Process '{program}' finished with exit code {exit_code}")
        sys.exit(1)

    program = " ".join([str(it) for it in args])
    print_verbose("running " + program)
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    (output, err) = process.communicate(input=stdin.encode())
    exit_code = process.wait()
    if exit_code != 0:
        _spawn_error(exit_code)
    return output.decode()


def filter_lockable_files(files):
    lockable_files = []

    files = files.strip()
    if files != "":
        locked = spawn(["git", "check-attr", "lockable", "--stdin"], files).strip()
        for line in locked.split("\n"):
            match = re.match(r"([^:]+): *([a-zA-Z0-9-_]+): *([a-zA-Z0-9-_]+)", line)
            if match[3] == "set":
                lockable_files.append(match[1])

    return lockable_files


def get_pipeline_secret():
    if "ZURU_PIPELINE_SECRET" not in os.environ:
        print("Environment variable ZURU_PIPELINE_SECRET not found", file=sys.stderr)
        sys.exit(1)
    return os.environ["ZURU_PIPELINE_SECRET"]


def get_upstream_branch(git_root):
    # Report an error in case of detached
    local_branch = spawn(
        ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"]
    ).strip()
    if local_branch == "HEAD":
        print(f"Repository: {git_root}", file=sys.stderr)
        print(
            f"ERROR: detached HEAD",
            file=sys.stderr,
        )
        sys.exit(1)

    status = spawn(
        [
            "git",
            "-C",
            str(git_root),
            "status",
            "--ignore-submodules=all",
            "--branch",
            "--porcelain=2",
        ]
    )

    # get parameter after prefix
    prefix = "# branch.upstream "
    status = [
        f.split(prefix)[1].strip() for f in status.split("\n") if f.startswith(prefix)
    ]

    if len(status) == 0 or not status[0].startswith("origin/"):
        print(f"Repository: {git_root}", file=sys.stderr)
        print(f"ERROR: no upstream configured for current branch", file=sys.stderr)
        print(
            f"You can set upstream with\ngit push -u origin {local_branch}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 'origin/feature/soul-split' became 'feature/soul-split'
    branch = status[0].split("/", 1)[1]

    print_verbose("found branch: " + branch)
    return branch


def get_current_path() -> str:
    """Returns the current value of "path" environment variable (Windows only)"""
    import winreg

    key = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, "Environment")
    return winreg.QueryValueEx(key, r"path")[0]


def is_valid_ref(ref):
    """Returns true if the specified name is valid git ref (eg: 'HEAD', 'refs/remotes/origin/develop')"""

    args = ["git", "cat-file", "-e", ref]
    process = subprocess.Popen(args, shell=False, stderr=subprocess.DEVNULL)
    exit_code = process.wait()
    return exit_code == 0


def set_verbose(_verbose):
    """Activate verbose logging, must be called right after argument parsing"""

    global verbose
    verbose = _verbose


def get_app_home() -> Path:
    """Returns the local home directory to store $path visible commands and user information"""

    return Path("~/.zuru-soft-lock").expanduser().absolute()


def _validate_and_get_authorization(user_data):
    exp = int(user_data.get("exp"))

    # margin of 60 seconds
    if time.time() > exp - 60:
        print_verbose("Token is expired")
        return None

    authorization = user_data.get("zsl-authorization")

    try:
        make_post(authorization, "/get-me", {})
    except NotAuthorizedError:
        print_verbose("Token is NOT valid")
        return None

    print_verbose("Token is valid")
    return authorization
