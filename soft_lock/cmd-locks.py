#!/bin/python
import argparse
import json
import os
import re
import sys
import functools
from fnmatch import fnmatch
from pathlib import Path

from . import lock_globals


def right_chop(s, suffix) -> str:
    if suffix and s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def _print_user(user):
    return f"{user['owner']['fullname']} (@{user['owner']['username']})"


def make_comparator(sort):
    valid_keys = ["path", "branch", "author", "p", "b", "a"]

    # python 2 cmp
    def cmp(a, b):
        return (a > b) - (a < b)

    def natsort_key(key):
        convert = lambda text: int(text) if text.isdigit() else text.lower()
        return [convert(c) for c in re.split("([0-9]+)", key)]

    def numeric_compare(x, y):
        for split in sort.split(","):
            if split in ["p", "path"]:
                f1 = natsort_key(x["filename"])
                f2 = natsort_key(y["filename"])
                if f1 != f2:
                    return cmp(f1, f2)
            elif split in ["b", "branch"]:
                f1 = natsort_key(x["branch"])
                f2 = natsort_key(y["branch"])
                if f1 != f2:
                    return cmp(f1, f2)
            elif split in ["a", "author"]:
                f1 = str.casefold(x["owner"]["username"])
                f2 = str.casefold(y["owner"]["username"])
                if f1 != f2:
                    return cmp(f1, f2)

        return 0

    # Validate format
    for s in sort.split(","):
        if s not in valid_keys:
            print(f"Invalid comparison key '{s}'")
            sys.exit(1)

    return functools.cmp_to_key(numeric_compare)


def main():
    """main entrypoint."""

    args = parse_arguments()
    lock_globals.set_verbose(args.verbose)

    repository = lock_globals.find_lfs_root()
    root = lock_globals.get_git_root()

    authorization = lock_globals.find_authorization(repository)
    response = lock_globals.make_post(
        authorization,
        "/get-locks",
        {
            "repository": repository,
            "output_json": True,
        },
    )

    if args.json:
        # Print raw json
        print(response.get("result"))
        return

    # Json row structure:
    # {"filename": "...", "branch": "...", "date_created": "iso date", "owner": {"username": "...", "fullname": "..."}
    lock_list = json.loads(response.get("result"))

    if not lock_list:
        # Se assume the server is gitlab.com
        print(f"No lock found for https://gitlab.com/{right_chop(repository, '.git')}")
        return

    # Filter by path
    if args.pathspec:
        # pathspec must use the same rules of `git status pathspec`
        lock_globals.print_verbose(f"Filtering by path-spech '{args.pathspec}'")

        # Special case for "."
        if args.pathspec == ".":
            relative_cwd = str(Path.cwd().relative_to(root)).replace("\\", "/")
            lock_list = [
                row for row in lock_list if row["filename"].startswith(relative_cwd)
            ]
        else:
            lock_list = [
                row for row in lock_list if fnmatch(row["filename"], args.pathspec)
            ]

    # Filter by mine
    if args.mine:
        username = lock_globals.get_gitlab_username()
        lock_globals.print_verbose(f"Filtering by username '{username}'")
        lock_list = [row for row in lock_list if row["owner"]["username"] == username]

    # Filter by current branch
    if args.this_branch:
        branch = lock_globals.get_upstream_branch(root)
        lock_globals.print_verbose(f"Filtering by branch '{branch}'")
        lock_list = [row for row in lock_list if row["branch"] == branch]

    if not lock_list:
        print(f"No lock found for the provided filters")
        return

    # Sort values
    sort_key = f"{args.sort},path" if isinstance(args.sort, str) else "path"
    lock_globals.print_verbose(f"Sorting by '{sort_key}'")
    lock_list = sorted(
        lock_list,
        key=make_comparator(sort_key),
    )

    # Convert relative paths
    if not args.full:
        lock_globals.print_verbose(f"Relativize paths in '{Path.cwd()}'")
        for row in lock_list:
            row["filename"] = os.path.relpath(root / row["filename"], Path.cwd())

    # Create table
    max_width = max([4] + [len(lock["filename"]) for lock in lock_list])
    max_branch = max([6] + [len(lock["branch"]) for lock in lock_list])
    template = "{0:%s}   {1:%s}   {2}" % (max_width, max_branch)

    # Table header + content
    rows = [template.format("File", "Branch", "Owner")] + [
        template.format(lock["filename"], lock["branch"], _print_user(lock))
        for lock in lock_list
    ]

    print("\n".join(rows))


def parse_arguments():
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        prog="git locks",
        description="Prints the list of currently locked files",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="\n".join(
            [
                "examples:",
                "  git locks --sort path     # Sort by file names",
                "  git locks --sort branch   # Sort by branch name",
                "  git locks --sort author   # Sort by lock owner",
                '  git locks "WBP_*"         # Show only widget blueprints',
            ]
        ),
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show verbose messages"
    )

    parser.add_argument(
        "pathspec",
        help='Pattern used to filter results (eg: "*.uasset", "BP_*", "Datatable/")',
        nargs="?",
    )

    parser.add_argument(
        "--full",
        help="paths shown will always be relative to the repository root instead of the current directory",
        action="store_true",
    )

    parser.add_argument(
        "--sort",
        "-s",
        help="Sort results (Choice of 'path', 'branch', 'author') (Default: 'path')",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Writes locks as json array.\n"
        "If the command returns with a non-zero exit code, error messages is written to stderr.\n"
        "When json is active most flags (like filter and sort) are not used and paths are always in full paths",
    )

    parser.add_argument(
        "--mine", action="store_true", help="Show only locks from the current user."
    )

    parser.add_argument(
        "--this_branch",
        "-b",
        action="store_true",
        help="Show only locks from the current branch.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
