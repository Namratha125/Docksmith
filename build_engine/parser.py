"""
parser.py — Reads a Docksmithfile and turns it into a list of instructions.

Member 2's job: Parse every line of the Docksmithfile.

Supported instructions: FROM, COPY, RUN, WORKDIR, ENV, CMD
Any other instruction causes an immediate error with the line number.
"""

import os

# Only these 6 instructions are allowed (as per the spec)
VALID_INSTRUCTIONS = {"FROM", "COPY", "RUN", "WORKDIR", "ENV", "CMD"}


def parse(context_path: str) -> list:
    """
    Parse the Docksmithfile inside context_path.

    Returns a list of instruction dicts, e.g.:
    [
        {"instruction": "FROM",    "args": "alpine:3.18",        "raw": "FROM alpine:3.18"},
        {"instruction": "WORKDIR", "args": "/app",               "raw": "WORKDIR /app"},
        {"instruction": "COPY",    "args": ". /app",             "raw": "COPY . /app"},
        {"instruction": "RUN",     "args": 'echo "hello"',       "raw": 'RUN echo "hello"'},
        {"instruction": "ENV",     "args": "NAME=Docksmith",     "raw": "ENV NAME=Docksmith"},
        {"instruction": "CMD",     "args": '["python","main.py"]',"raw": 'CMD ["python","main.py"]'},
    ]

    Raises:
        FileNotFoundError — if no Docksmithfile found
        SyntaxError      — if an unknown instruction is used (with line number)
        SyntaxError      — if a line has no arguments
    """
    docksmithfile_path = os.path.join(context_path, "Docksmithfile")

    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(
            f"No Docksmithfile found in '{context_path}'."
        )

    instructions = []

    with open(docksmithfile_path, "r") as f:
        lines = f.readlines()

    for line_num, raw_line in enumerate(lines, start=1):
        # Strip whitespace and carriage returns (Windows line endings)
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        # Split into the instruction keyword and the rest
        parts = line.split(None, 1)  # split on first whitespace only
        keyword = parts[0].upper()

        # Validate the instruction keyword
        if keyword not in VALID_INSTRUCTIONS:
            raise SyntaxError(
                f"Docksmithfile line {line_num}: Unknown instruction '{parts[0]}'. "
                f"Supported: {', '.join(sorted(VALID_INSTRUCTIONS))}"
            )

        # Make sure there are arguments after the keyword
        if len(parts) < 2 or not parts[1].strip():
            raise SyntaxError(
                f"Docksmithfile line {line_num}: Instruction '{keyword}' requires arguments."
            )

        args = parts[1].strip()

        instructions.append({
            "instruction": keyword,
            "args": args,
            "raw": line,        # full original line (used for cache key)
            "line_num": line_num,
        })

    if not instructions:
        raise SyntaxError("Docksmithfile is empty or contains only comments.")

    # Must start with FROM
    if instructions[0]["instruction"] != "FROM":
        raise SyntaxError(
            f"Docksmithfile must start with a FROM instruction. "
            f"Got '{instructions[0]['instruction']}' on line {instructions[0]['line_num']}."
        )

    return instructions
