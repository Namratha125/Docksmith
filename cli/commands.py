"""
commands.py — The 4 command handler functions.
Member 1's core logic file.

Each function:
  1. Validates the user's input
  2. Calls another member's module (via interfaces.py)
  3. Uses formatter.py to print results
"""

import os
from cli import formatter
from cli.interfaces import build_image, list_images, delete_image, run_container


# ── docksmith build ───────────────────────────────────────────────────────────

def cmd_build(tag: str, context: str, no_cache: bool):
    """
    Handle: docksmith build -t myapp:latest .

    Steps:
      1. Validate the tag format (must be "name:tag")
      2. Check the context directory exists
      3. Check a Docksmithfile exists inside it
      4. Call Member 2's build_image()
      5. Print each build step with CACHE HIT / CACHE MISS
      6. Print success message
    """
    # Step 1: Validate tag format
    validate_tag(tag)

    # Step 2: Check context directory exists
    if not os.path.isdir(context):
        raise FileNotFoundError(
            f"Build context '{context}' is not a directory. "
            f"Run this command from your project folder, e.g.: docksmith build -t myapp:latest ."
        )

    # Step 3: Check Docksmithfile exists
    docksmithfile_path = os.path.join(context, "Docksmithfile")
    if not os.path.isfile(docksmithfile_path):
        raise FileNotFoundError(
            f"No Docksmithfile found in '{context}'. "
            f"Create a file named 'Docksmithfile' in your project directory."
        )

    # Print build start
    formatter.print_build_start(tag, context)
    if no_cache:
        formatter.print_no_cache_warning()

    # Step 4: Call Member 2's build engine
    result = build_image(tag=tag, context_path=context, no_cache=no_cache)

    # Step 5: Print each step
    steps = result.get("steps", [])
    total = len(steps)
    for i, step in enumerate(steps, start=1):
        formatter.print_build_step(
            step_num=i,
            total_steps=total,
            instruction=step["instruction"],
            cache_hit=step.get("cache_hit"),   # None for FROM/WORKDIR/ENV/CMD
            duration=step.get("duration"),
)

    # Step 6: Print success
    formatter.print_build_success(result.get("image_digest", "unknown"))


# ── docksmith images ──────────────────────────────────────────────────────────

def cmd_images():
    """
    Handle: docksmith images

    Steps:
      1. Call Member 3's list_images()
      2. Print formatted table
    """
    images = list_images()
    formatter.print_images_table(images)


# ── docksmith run ─────────────────────────────────────────────────────────────

def cmd_run(image: str, env_overrides: dict):
    """
    Handle: docksmith run myapp:latest
            docksmith run -e NAME=World myapp:latest

    Steps:
      1. Validate tag format
      2. Print run start info
      3. Call Member 4's run_container()
      4. Print exit status
    """
    # Validate format
    validate_tag(image)

    # Print info
    formatter.print_run_start(image)
    if env_overrides:
        formatter.print_run_env(env_overrides)

    # Call Member 4
    exit_code = run_container(image=image, env_overrides=env_overrides)

    # Print result
    formatter.print_run_complete(exit_code)


# ── docksmith rmi ─────────────────────────────────────────────────────────────

def cmd_rmi(image: str):
    """
    Handle: docksmith rmi myapp:latest

    Steps:
      1. Validate tag format
      2. Call Member 3's delete_image()
      3. Print success message
    """
    # Validate format
    validate_tag(image)

    # Call Member 3
    delete_image(image)

    # Print success
    formatter.print_rmi_success(image)


# ── Helper ────────────────────────────────────────────────────────────────────

def validate_tag(tag: str):
    """
    Make sure a tag is in the format "name:tag".
    Raises ValueError with a helpful message if not.

    Valid:   "myapp:latest"  "webapp:v1.0"
    Invalid: "myapp"  ":latest"  ""  "my:app:latest"
    """
    if not tag:
        raise ValueError("Image name cannot be empty.")

    if ":" not in tag:
        raise ValueError(
            f"Invalid image name '{tag}'. "
            f"Format must be NAME:TAG, e.g. 'myapp:latest'"
        )

    parts = tag.split(":")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid image name '{tag}'. "
            f"Use exactly one colon, e.g. 'myapp:latest'"
        )

    name, tag_part = parts
    if not name:
        raise ValueError(f"Image name cannot be empty in '{tag}'.")
    if not tag_part:
        raise ValueError(f"Tag cannot be empty in '{tag}'. Try 'myapp:latest'.")
