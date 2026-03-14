"""
formatter.py — All the print/display functions for Docksmith CLI output.
Member 1's job: Make the terminal output look clean and professional.

This file controls how EVERYTHING looks in the terminal.
Other members do NOT print directly — they return data, and this file prints it.
"""

from datetime import datetime


# ANSI colour codes for terminal output
# These make text coloured in most terminals (Linux, macOS, Windows Terminal)
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ── Build output ──────────────────────────────────────────────────────────────

def print_build_step(step_num: int, total_steps: int, instruction: str, cache_hit: bool):
    """
    Print a single build step line.

    Example output:
        Step 2/5 : COPY . /app  [CACHE HIT]
        Step 3/5 : RUN echo hello  [CACHE MISS]
    """
    cache_label = f"{GREEN}[CACHE HIT]{RESET}" if cache_hit else f"{YELLOW}[CACHE MISS]{RESET}"
    print(f"Step {step_num}/{total_steps} : {instruction}  {cache_label}")


def print_build_success(image_digest: str):
    """
    Print the final success message after a build completes.

    Example output:
        Successfully built sha256:a3f9b2c1
    """
    short_digest = image_digest[:19] if len(image_digest) > 19 else image_digest
    print(f"{GREEN}Successfully built {short_digest}{RESET}")


def print_build_start(tag: str, context: str):
    """
    Print the first line when a build begins.

    Example output:
        Building image myapp:latest from .
    """
    print(f"Building image {BOLD}{tag}{RESET} from {CYAN}{context}{RESET}")


def print_no_cache_warning():
    """Shown when --no-cache flag is used."""
    print(f"{YELLOW}Cache disabled — all steps will be rebuilt{RESET}")


# ── Images table ──────────────────────────────────────────────────────────────

def print_images_table(images: list):
    """
    Print a formatted table of all images.

    images: a list of dicts from Member 3's storage module.
    Each dict has: name, tag, id, created (datetime or ISO string)

    Example output:
        NAME      TAG       IMAGE ID        CREATED
        myapp     latest    a3f9b2c1d4e5    2026-03-10
        webapp    v1.0      f1e2d3c4b5a6    2026-03-09
    """
    if not images:
        print("No images found. Build one with: docksmith build -t myapp:latest .")
        return

    # Column widths — wide enough for most names
    COL_NAME    = 16
    COL_TAG     = 12
    COL_ID      = 16
    COL_CREATED = 12

    # Header row
    header = (
        f"{'NAME':<{COL_NAME}}"
        f"{'TAG':<{COL_TAG}}"
        f"{'IMAGE ID':<{COL_ID}}"
        f"{'CREATED':<{COL_CREATED}}"
    )
    print(BOLD + header + RESET)

    # One row per image
    for img in images:
        # Shorten the digest so it fits the column
        short_id = img.get("id", "")[:12]

        # Format the created date nicely
        created = img.get("created", "")
        if isinstance(created, datetime):
            created_str = created.strftime("%Y-%m-%d")
        else:
            # If it's already a string, just take the date part
            created_str = str(created)[:10]

        row = (
            f"{img.get('name', ''):<{COL_NAME}}"
            f"{img.get('tag', ''):<{COL_TAG}}"
            f"{short_id:<{COL_ID}}"
            f"{created_str:<{COL_CREATED}}"
        )
        print(row)


# ── Run output ────────────────────────────────────────────────────────────────

def print_run_start(image: str):
    """Shown when a container starts."""
    print(f"Running container from image {BOLD}{image}{RESET}")


def print_run_env(env: dict):
    """Show the environment variables being injected (debug info)."""
    if env:
        print(f"{DIM}Environment overrides: {env}{RESET}")


def print_run_complete(exit_code: int):
    """Show exit status after container finishes."""
    if exit_code == 0:
        print(f"{GREEN}Container exited successfully (code 0){RESET}")
    else:
        print(f"{YELLOW}Container exited with code {exit_code}{RESET}")


# ── Remove image output ───────────────────────────────────────────────────────

def print_rmi_success(image: str):
    """Shown after an image is deleted."""
    print(f"Deleted image: {image}")


# ── Error messages ────────────────────────────────────────────────────────────

def print_error(message: str):
    """
    Print an error in red.
    Called from main.py whenever a command raises an exception.
    """
    print(f"{RED}Error: {message}{RESET}", flush=True)


def print_warning(message: str):
    """Print a yellow warning (non-fatal)."""
    print(f"{YELLOW}Warning: {message}{RESET}")
