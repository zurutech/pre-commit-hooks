#!/bin/python

import os
from pathlib import Path
import shutil

from . import lock_globals


def find_bash_config():
    """Returns the config filename of the current shell or None if the bash is unknown"""
    shell = os.getenv("SHELL")
    if shell is not None:
        bash_file_name = Path(shell).name
        if bash_file_name == "bash":
            return ".bashrc"
        if bash_file_name == "zsh":
            return ".zshrc"
    return None


def main():
    """main entrypoint."""

    source = Path(__file__).parent / "client"
    destination = lock_globals.get_app_home()
    print(f"Installing Zuru Soft Lock into directory {destination}")

    destination.mkdir(parents=True, exist_ok=True)

    for file in lock_globals.all_files:
        shutil.copy(source / file, destination / file)

    # On windows add ~/.zuru-soft-lock on path
    # otherwise ask the user to do it
    find_bash_config()
    if os.name == "nt":
        current_path = lock_globals.get_current_path()
        if str(destination) not in current_path.split(";"):
            print(f"  - Adding '{destination}' to path")
            lock_globals.spawn(["setx", "path", f"{current_path};{destination}"])
    else:
        # Assuming unix
        line = f"export PATH=$PATH:{destination}"
        config_file = find_bash_config()
        if config_file is None:
            print(f"  - Please add '{destination}' to $PATH directory")
        else:
            zsh_filename = Path.home() / config_file
            source = (
                open(zsh_filename).read().splitlines() if zsh_filename.exists() else []
            )

            if line not in source:
                print(f"  - Adding '{destination}' to ~/{config_file}")
                with open(zsh_filename, "a") as f:
                    f.write(f"# Zuru soft lock integration\n{line}\n")
            else:
                print(f"  - Skip add '{destination}' in ~/{config_file}")

    print("  - Please restart your terminal")
    print("  - Done")


if __name__ == "__main__":
    main()
