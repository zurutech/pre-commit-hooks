#!/bin/python
import argparse
import sys

from . import lock_globals


def main():
    """main entrypoint."""

    args = parse_arguments()
    lock_globals.set_verbose(args.verbose)

    # Find the path
    for path in lock_globals.get_clean_paths(args.path, verify_presence=True):
        # Get git repository from path
        git_root = lock_globals.get_git_root_from_dir(path)
        lock_globals.print_verbose(f"Found git repository {git_root}")

        relative_path = lock_globals.get_repository_path(path, git_root)
        repository = lock_globals.find_lfs_root(git_root)
        branch = lock_globals.get_upstream_branch(git_root)

        lock_globals.print_verbose(
            f"Locking file '{relative_path}' in repository '{repository}' in branch '{branch}'"
        )

        # Run api
        body = {
            "repository": repository,
            "fullname": lock_globals.get_full_name(),
            "path": relative_path,
            "branch": branch,
        }
        authorization = lock_globals.find_authorization(repository)
        response = lock_globals.make_post(
            authorization, "/lock", body, return_error=True
        )

        # On error, print error and continue
        if isinstance(response.get("error"), str):
            print(response.get("error"), file=sys.stderr)
            continue

        print(response.get("result"))


def parse_arguments():
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        prog="git lock",
        description="Lock the specified file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("path", metavar="<path>", nargs="+")

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show verbose messages"
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
