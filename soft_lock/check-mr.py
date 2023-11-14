#!/bin/python
import argparse
import sys

from . import lock_globals


def main():
    """main entrypoint."""

    args = parse_arguments()

    files = lock_globals.spawn(
        ["git", "diff", "--name-only", args.ref1, args.ref2]
    ).strip()
    files = lock_globals.filter_lockable_files(files)
    if len(files) == 0:
        # No file to check
        sys.exit(0)

    # for pipeline use only
    authorization = lock_globals.get_pipeline_secret()
    repository = lock_globals.find_lfs_root()
    print("File checked: \n - " + "\n - ".join(files))
    body = {"repository": repository, "files": files, "branch": args.branch}
    lock_globals.make_post(authorization, "/check_mr", body)


def parse_arguments():
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Verify that all files modified between two revisions are correctly locked",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("ref1", metavar="<ref1>")
    parser.add_argument("ref2", metavar="<ref2>")
    parser.add_argument("--branch", metavar="<branch>", required=True)

    return parser.parse_args()


if __name__ == "__main__":
    main()
