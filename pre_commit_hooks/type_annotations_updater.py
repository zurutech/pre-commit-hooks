# Copyright (c) 2014-2023 Zuru Tech HK Limited, All rights reserved.

import argparse
import fnmatch
import os
import subprocess
import sys
from argparse import ArgumentParser


def get_arguments() -> argparse.Namespace:
    parser = ArgumentParser(
        description="Update the type annotations of all the C++ and C# files"
    )
    parser.add_argument(
        "--folders",
        default=[],
        type=str,
        nargs="+",
        help="Root folders that will be traversed",
    )

    args = parser.parse_args()
    return args


def get_file_folders(root_folders: list[str], filename: str) -> list[str]:
    # Create a list to store the file paths
    file_folders = []

    # Walk through the directory and its subdirectories
    for root_folder in root_folders:
        for dir_path, _, filenames in os.walk(root_folder):
            for _ in fnmatch.filter(filenames, filename):
                file_folders.append(dir_path)

    return file_folders


def main() -> int:
    args = get_arguments()
    folders = get_file_folders(args.folders, "test_type_annotations.py")
    root = os.getcwd()

    for folder in folders:
        os.chdir(f"./{folder}")
        subprocess.run(["monkeytype", "run", "test_type_annotations.py"])
        result = subprocess.run(
            ["monkeytype", "list-modules"], stdout=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            modules = result.stdout.split("\n")
            for module in modules:
                subprocess.run(["monkeytype", "apply", module])
        os.chdir(root)

    return 1


if __name__ == "__main__":
    sys.exit(main())
