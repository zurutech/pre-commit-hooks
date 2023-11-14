#!/bin/python

import os
import shutil

from . import lock_globals


def main():
    """main entrypoint."""

    destination = lock_globals.get_app_home()
    print(f"Uninstalling Zuru Soft Lock from {destination}")

    # remove files
    for file in lock_globals.all_files:
        join = destination / file
        if join.exists():
            os.remove(join)

    # remove generated python cache
    pycache = destination / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)

    # remove directory
    shutil.rmtree(destination, ignore_errors=True)

    # remove from path
    if os.name == "nt":
        current_path = lock_globals.get_current_path().split(";")
        if str(destination) in current_path:
            current_path = [
                value for value in current_path if value != str(destination)
            ]
            print(f"  - Removing '{destination}' from path")
            lock_globals.spawn(["setx", "path", ";".join(current_path)])


if __name__ == "__main__":
    main()
