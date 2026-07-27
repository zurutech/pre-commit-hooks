# Copyright (c) 2014-2026 Zuru Tech HK Limited, All rights reserved.

"""................ Pre Commit Hook for String Table Generator ....................
This script is needed to automate the execution of the script for generating the string table csv files from the error csv files. `Content/Errors/StringTables` is a generated artifact: ``string_table_generator.py`` turns every ``Content/Errors/ErrorTables/*.csv`` into the matching StringTable csv used by UE localization. 
The two folders must therefore stay in sync. This hook inspects the *staged* changes and fails when:    
    1. The ErrorTables changed but the StringTables were left untouched (the generated tables were not refreshed).
    2. Both folders changed, but running ``string_table_generator.py`` on the current ErrorTables produces StringTables that differ from the ones being committed (the staged StringTables are not what the generator would produce).
The working tree is never modified: the generator is run against an isolated copy.
Since this script should be run after every change to the files in the Content/Errors folder, this pre commit hook allows to guarantee the execution of the csv script once the new file are pushed onto git.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Layout, relative to the git repository root.
PROJECT_SUBDIR = "Dreamcatcher"
ERRORS_RELPATH = Path("Content") / "Errors"
ERROR_TABLES_DIRNAME = "ErrorTables"
STRING_TABLES_DIRNAME = "StringTables"

# The generator lives next to this hook.
GENERATOR = Path(__file__).resolve().parent / "string_table_generator.py"

PREFIX = "error-string-tables: "

def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

def _fail(message):
    print(PREFIX + message, file=sys.stderr)
    sys.exit(1)

def _git_root():
    result = _run(["git", "rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        _fail("not inside a git repository.")
    return Path(result.stdout.strip())

def _staged_paths(root):
    result = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"], cwd=root,)
    if result.returncode != 0:
        _fail("failed to read staged changes:\n" + result.stderr)
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]

def _is_under(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False

def _csv_names_under(paths, folder):
    """Basenames of the staged .csv files located under ``folder``."""
    return {p.name for p in paths if p.suffix == ".csv" and _is_under(p, folder)}


def _normalize(text):
    # Compare on content, ignoring line-ending differences: git may check the file out with CRLF, while the generator always writes LF.
    return text.replace("\r\n", "\n").replace("\r", "\n")

def _read(path):
    try:
        return _normalize(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _generate_expected(error_tables, tmp_root):
    """Run the generator on a copy of the ErrorTables and return the generated folder. The real StringTables folder is left untouched: the generator writes into ``tmp_root``."""
    tmp_error_tables = tmp_root / ERRORS_RELPATH / ERROR_TABLES_DIRNAME
    tmp_error_tables.mkdir(parents=True, exist_ok=True)
    for csv_file in error_tables.glob("*.csv"):
        shutil.copy2(csv_file, tmp_error_tables / csv_file.name)

    result = _run([sys.executable, str(GENERATOR)],env={**os.environ, "PROJECT_PATH": str(tmp_root)},)
    if result.returncode != 0:
        _fail("string_table_generator.py failed to run:\n"+ result.stdout+ result.stderr)
    return tmp_root / ERRORS_RELPATH / STRING_TABLES_DIRNAME

def main():
    if not GENERATOR.is_file():
        _fail(f"generator not found at {GENERATOR}.")

    root = _git_root()
    errors_dir = root / PROJECT_SUBDIR / ERRORS_RELPATH
    error_tables = errors_dir / ERROR_TABLES_DIRNAME
    string_tables = errors_dir / STRING_TABLES_DIRNAME

    if not error_tables.is_dir():
        _fail(f"ErrorTables folder not found at {error_tables}.")
    error_tables_rel = Path(PROJECT_SUBDIR) / ERRORS_RELPATH / ERROR_TABLES_DIRNAME
    string_tables_rel = Path(PROJECT_SUBDIR) / ERRORS_RELPATH / STRING_TABLES_DIRNAME

    staged = _staged_paths(root)
    changed_error_names = _csv_names_under(staged, error_tables_rel)
    changed_string_names = _csv_names_under(staged, string_tables_rel)

    # Nothing to enforce unless the ErrorTables changed.
    if not changed_error_names:
        return 0

    regenerate_hint = (
         "\n\nRegenerate the StringTables and stage them:\n"
         f'    PROJECT_PATH="{root / PROJECT_SUBDIR}" "{sys.executable}" "{GENERATOR}"\n'
         f"    git add {string_tables_rel.as_posix()}/"
     )

    # Rule 1: the ErrorTables changed but the StringTables were not refreshed.
    if not changed_string_names:
        _fail("ErrorTables were modified but no StringTables change is staged."+ regenerate_hint)

    # Rule 2: both folders changed -> the staged StringTables must equal what the generator produces from the current ErrorTables. Only the files touched by this commit are checked, so unrelated pre-existing state cannot fail the commit.
    relevant_names = sorted(changed_error_names | changed_string_names)
    with tempfile.TemporaryDirectory(prefix="error-string-tables-") as tmp:
        expected_dir = _generate_expected(error_tables, Path(tmp))
        expected_dir = _generate_expected(error_tables, Path(tmp))

        mismatches = []
        for name in relevant_names:
            expected = _read(expected_dir / name)
            actual = _read(string_tables / name)
            if expected is None:
                mismatches.append(f"  {name}: the generator does not produce this file ""(its ErrorTable is missing/deleted;delete the StringTable too)")
            elif actual is None:
                mismatches.append(f"  {name}: missing from StringTables")
            elif expected != actual:
                mismatches.append(f"  {name}: differs from the generator output")

    if mismatches:
        _fail("the staged StringTables do not match string_table_generator.py output:\n"+ "\n".join(mismatches)+ regenerate_hint)

    return 0

if __name__ == "__main__":
    sys.exit(main())