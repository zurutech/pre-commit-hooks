# This file is installed on ~/.zuru-soft-lock to enable integration

import os.path
import subprocess
import sys

FIND_PATH = ".gitlab/soft-lock"


def find_lock_root():
    directory = os.path.abspath("")

    while True:
        root = os.path.abspath(os.path.join(directory, FIND_PATH))
        if os.path.isdir(root):
            return root

        new_dir = os.path.dirname(directory)
        if new_dir == directory:
            print(
                "Soft lock root '{}' not found in parents of '{}'".format(
                    FIND_PATH, os.path.abspath("")
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        directory = new_dir


def main():
    root = find_lock_root()
    python_file = os.path.join(root, f"cmd-{sys.argv[1]}.py")
    sys.exit(subprocess.call([sys.executable, python_file] + sys.argv[2:]))


main()
