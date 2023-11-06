import re
import sys
import io


def main():
    for file in sys.argv[1:]:
        if not file.startswith("-"):
            verify_file(file)


def verify_file(file_name):
    with io.open(file_name, "r", encoding="utf-8") as f:
        content = f.read()

    # If the "generated" header is not prefixed by a newline, add one.
    replaced = re.sub(
        r'(#include \"[^"]+")\n(#include \".*\.generated.h")', r"\1\n\n\2", content
    )
    if replaced != content:
        print(f"Fixing {file_name}")
        # Write the new content with unix style EOL (otherwise, on windows it would be "\r\n")
        with io.open(file_name, "w", newline="\n") as f:
            f.write(replaced)


if __name__ == "__main__":
    main()
