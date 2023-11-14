#!/usr/bin/env python

from . import lock_globals


def get_modified_files():
    """Return the list of modified files."""

    if lock_globals.is_valid_ref("MERGE_HEAD"):
        # If this is a merge commit, check only conflicted files
        # Currently, conflicts which has been resolved by choosing one side or the other are not checked
        write_tree = lock_globals.spawn(["git", "write-tree"]).strip()
        return lock_globals.spawn(
            ["git", "diff", "--name-only", str(write_tree), "HEAD", "MERGE_HEAD"]
        ).strip()

    if lock_globals.is_valid_ref("REBASE_HEAD"):
        # Special case: during "interactive rebase" all commits are created without being in a specific branch
        # In this case no lock is required
        return ""

    # For normal commit, check modified files between HEAD (last commit) and the cache
    return lock_globals.spawn(
        ["git", "diff-index", "--cached", "--name-only", "HEAD"]
    ).strip()


def main():
    """main entrypoint."""

    files = lock_globals.filter_lockable_files(get_modified_files())
    if not files:
        # No file to check
        exit(0)

    print("Checking:\n- %s" % "\n- ".join(files))
    git_root = lock_globals.get_git_root()
    repository = lock_globals.find_lfs_root()
    body = {
        "repository": repository,
        "files": files,
        "branch": lock_globals.get_upstream_branch(git_root),
    }
    authorization = lock_globals.find_authorization(repository)
    lock_globals.make_post(authorization, "/pre-commit", body)

    # no error means ok


if __name__ == "__main__":
    main()
