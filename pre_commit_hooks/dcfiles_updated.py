# Copyright (c) 2014-2024 Zuru Tech HK Limited, All rights reserved.

"""pre-commit hook that verifies if the .dc files passed are updated to the latest version"""
import io
import json
import re
import sys


def verify_file(file_name, version):
    """Verifies if the .dc file schema is at the passed version"""
    with io.open(file_name, "r", encoding="utf-8") as fp:
        dcfile = json.load(fp)

    if not dcfile["schema"].endswith(f"v{version}/schema.json"):
        return False

    return True


def main():
    """Entrypoint"""

    version = ""
    with io.open(
        "Dreamcatcher/Plugins/BIMCore/Source/DCInterfaces/Public/Source/ExportData/ExpStructs.h",
        "r",
        encoding="utf-8",
    ) as fp:
        for line in fp:
            if "DCFileVersion" in line:
                result = re.search(r"DCFileVersion = \"v(\d+)\.(\d+)\.(\d+)\"", line)
                if not result:
                    print("Unable to extract DCFileVersion value", file=sys.stderr)
                    return 1
                version = f"{result.group(1)}.{result.group(2)}.{result.group(3)}"
                break
    if not version:
        print("Unable to find DCFileVersion", file=sys.stderr)
        return 1

    for dcfile in sys.argv[1:]:
        if not dcfile.startswith("-"):
            if not verify_file(dcfile, version):
                print(
                    f"{dcfile} not updated to the latest schema version: {version}",
                    file=sys.stderr,
                )
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
