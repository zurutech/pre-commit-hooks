# Copyright (c) 2014-2026 Zuru Tech HK Limited, All rights reserved.

"""................ Pre Commit Hook for String Table Generator ....................
This script is needed to automate the execution of the script for generating the string table csv files from the error csv files. 
Since this script should be run after every change to the files in the Content/Errors folder, this pre commit hook allows to guarantee the execution of the csv script once the new file are pushed onto git.
"""

import subprocess
import sys
from pathlib import Path

""" Constants """

# The wrapper lives next to the generator inside Content/Errors, so every path
# is resolved from this file's location rather than the current working
# directory (pre-commit runs hooks from the repository root).
ERRORS_DIR = Path(__file__).resolve().parent
GENERATOR = ERRORS_DIR / "string_table_generator.py"
ERROR_TABLES_DIR = ERRORS_DIR / "ErrorTables"
STRING_TABLES_DIR = ERRORS_DIR / "StringTables"

""" Functions """

def _fail(message):
    print(f"[string-tables] {message}", file=sys.stderr)
    return 1

def main():
    if not GENERATOR.is_file():
        return _fail(f"Generator not found: {GENERATOR}")

    if not ERROR_TABLES_DIR.is_dir():
        return _fail(f"ErrorTables folder not found: {ERROR_TABLES_DIR}")

    error_tables = sorted(ERROR_TABLES_DIR.glob("*.csv"))
    if not error_tables:
        print("[string-tables] No error tables found, nothing to generate.")
        return 0

    # The generator resolves its own paths from the current working directory,
    # so it must run with Content/Errors as the working directory. Running it as
    # a subprocess also isolates the sys.exit() calls it makes internally.
    print(f"[string-tables] Regenerating from {len(error_tables)} error table(s)...")
    result = subprocess.run([sys.executable, str(GENERATOR)], cwd=str(ERRORS_DIR))
    if result.returncode != 0:
        return _fail("string_table_generator.py failed.")

    # The generator always exits 0 and never reports whether it changed anything,
    # so git is the source of truth for detecting a diff (modified or new files).
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(STRING_TABLES_DIR)],
        cwd=str(ERRORS_DIR),
        capture_output=True,
        text=True,
    )

    if status.returncode != 0:
        return _fail("Unable to check the git status of the String Tables.")

    if status.stdout.strip():
        changed = "\n".join(f"  {line}" for line in status.stdout.strip().splitlines())
        return _fail(
            "String Tables were out of date and have been regenerated:\n"
            f"{changed}\n"
            "Stage them (git add Content/Errors/StringTables) and commit again."
        )

    print("[string-tables] String Tables are up to date.")
    return 0

if __name__ == "__main__":
    sys.exit(main())