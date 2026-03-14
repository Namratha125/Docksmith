"""
main.py — Entry point for the Docksmith CLI
Member 1's job: Parse the command the user typed and call the right function.

Usage:
    python -m docksmith build -t myapp:latest .
    python -m docksmith images
    python -m docksmith run myapp:latest
    python -m docksmith rmi myapp:latest
"""

import argparse
import sys
from cli.commands import cmd_build, cmd_images, cmd_run, cmd_rmi
from cli.formatter import print_error


def create_parser():
    """
    Set up all the CLI commands and their flags.
    argparse handles the annoying work of reading sys.argv for us.
    """
    parser = argparse.ArgumentParser(
        prog="docksmith",
        description="Docksmith — a mini Docker system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  docksmith build -t myapp:latest .
  docksmith images
  docksmith run myapp:latest
  docksmith run -e NAME=World myapp:latest
  docksmith rmi myapp:latest
        """
    )

    # Each subcommand gets its own sub-parser
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True  # User must type a command

    # ── docksmith build ───────────────────────────────────────────────────────
    build_parser = subparsers.add_parser(
        "build",
        help="Build an image from a Docksmithfile"
    )
    build_parser.add_argument(
        "-t", "--tag",
        required=True,
        metavar="NAME:TAG",
        help='Name and tag for the image, e.g. "myapp:latest"'
    )
    build_parser.add_argument(
        "context",
        nargs="?",
        default=".",
        help="Build context directory (default: current directory)"
    )
    build_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable build cache — every step is a CACHE MISS"
    )

    # ── docksmith images ──────────────────────────────────────────────────────
    subparsers.add_parser(
        "images",
        help="List all built images"
    )

    # ── docksmith run ─────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run",
        help="Run a container from an image"
    )
    run_parser.add_argument(
        "image",
        metavar="NAME:TAG",
        help='Image to run, e.g. "myapp:latest"'
    )
    run_parser.add_argument(
        "-e", "--env",
        action="append",        # allows -e A=1 -e B=2
        metavar="KEY=VALUE",
        default=[],
        help="Set environment variables (can be used multiple times)"
    )

    # ── docksmith rmi ─────────────────────────────────────────────────────────
    rmi_parser = subparsers.add_parser(
        "rmi",
        help="Remove an image"
    )
    rmi_parser.add_argument(
        "image",
        metavar="NAME:TAG",
        help='Image to remove, e.g. "myapp:latest"'
    )

    return parser


def main():
    """
    The main function — this runs when the user types any docksmith command.
    Steps:
      1. Parse what the user typed
      2. Route to the correct command function
      3. Print any errors nicely
    """
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Route to the right command based on what the user typed
        if args.command == "build":
            cmd_build(
                tag=args.tag,
                context=args.context,
                no_cache=args.no_cache
            )

        elif args.command == "images":
            cmd_images()

        elif args.command == "run":
            # Parse -e KEY=VALUE flags into a dict: {"KEY": "VALUE"}
            env_overrides = parse_env_flags(args.env)
            cmd_run(
                image=args.image,
                env_overrides=env_overrides
            )

        elif args.command == "rmi":
            cmd_rmi(image=args.image)

    except KeyboardInterrupt:
        # User pressed Ctrl+C
        print("\nCancelled.")
        sys.exit(1)

    except Exception as e:
        # Something went wrong — print it nicely and exit with error code
        print_error(str(e))
        sys.exit(1)


def parse_env_flags(env_list: list) -> dict:
    """
    Convert a list like ["NAME=World", "PORT=8080"]
    into a dict like {"NAME": "World", "PORT": "8080"}.

    Called when the user uses: docksmith run -e NAME=World -e PORT=8080
    """
    result = {}
    for item in env_list:
        if "=" not in item:
            raise ValueError(
                f"Invalid -e flag: '{item}'. "
                f"Format must be KEY=VALUE (e.g. -e NAME=World)"
            )
        key, _, value = item.partition("=")
        if not key:
            raise ValueError(f"Invalid -e flag: '{item}'. Key cannot be empty.")
        result[key] = value
    return result


if __name__ == "__main__":
    main()
