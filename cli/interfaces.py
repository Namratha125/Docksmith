"""
interfaces.py — Stub interfaces for the other 3 members' modules.

WHY THIS FILE EXISTS:
    Your CLI code needs to call Member 2, 3, and 4's code.
    But they haven't written it yet!

    This file provides FAKE versions of their functions so your
    CLI code runs and can be tested right now.

    When a member finishes their module, they REPLACE the stub
    below with a real import from their module.

HOW TO SWAP IN REAL CODE:
    When Member 2 finishes build_engine/builder.py, change:
        # STUB
        def build_image(...): ...
    to:
        from build_engine.builder import build_image

    Same for Members 3 and 4.
"""


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 2 — Build Engine
# Replace with: from build_engine.builder import build_image
# ══════════════════════════════════════════════════════════════════════════════

def build_image(tag: str, context_path: str, no_cache: bool = False):
    """
    Build an image from a Docksmithfile.

    Parameters:
        tag          — "myapp:latest"
        context_path — path to the directory with the Docksmithfile (usually ".")
        no_cache     — if True, ignore cache and rebuild everything

    Returns:
        A dict with build results:
        {
            "steps": [
                {"instruction": "FROM alpine:3.18", "cache_hit": False},
                {"instruction": "COPY . /app",      "cache_hit": True},
                ...
            ],
            "image_digest": "sha256:a3f9b2c1d4e5..."
        }

    Raises:
        FileNotFoundError — if no Docksmithfile found in context_path
        ValueError        — if an unsupported instruction is used
        RuntimeError      — if a RUN command fails
    """
    # ── STUB — DELETE THIS BLOCK WHEN MEMBER 2 IS READY ──────────────────────
    print(f"  [STUB] Member 2 not integrated yet")
    print(f"  [STUB] Would build '{tag}' from '{context_path}'")
    return {
        "steps": [
            {"instruction": "FROM alpine:3.18", "cache_hit": False},
            {"instruction": "COPY . /app",      "cache_hit": False},
            {"instruction": "RUN echo hello",   "cache_hit": False},
        ],
        "image_digest": "sha256:stub000000000000000000000000000000000000000000000000000000000000000"
    }
    # ─────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 3 — Layer & Image Storage
# Replace with: from storage.image_store import list_images, delete_image
# ══════════════════════════════════════════════════════════════════════════════

def list_images():
    """
    Return a list of all stored images.

    Returns:
        A list of dicts, one per image:
        [
            {
                "name":    "myapp",
                "tag":     "latest",
                "id":      "a3f9b2c1d4e5",
                "created": "2026-03-10T14:30:00"
            },
            ...
        ]
    """
    # ── STUB — DELETE THIS BLOCK WHEN MEMBER 3 IS READY ──────────────────────
    print("  [STUB] Member 3 not integrated yet — showing fake images")
    return [
        {"name": "myapp",  "tag": "latest", "id": "a3f9b2c1d4e5", "created": "2026-03-10"},
        {"name": "webapp", "tag": "v1.0",   "id": "f1e2d3c4b5a6", "created": "2026-03-09"},
    ]
    # ─────────────────────────────────────────────────────────────────────────


def delete_image(image: str):
    """
    Delete an image and its associated layers.

    Parameters:
        image — "myapp:latest"

    Raises:
        FileNotFoundError — if the image doesn't exist
    """
    # ── STUB — DELETE THIS BLOCK WHEN MEMBER 3 IS READY ──────────────────────
    print(f"  [STUB] Member 3 not integrated yet — would delete '{image}'")
    # ─────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# MEMBER 4 — Container Runtime
# Replace with: from runtime.runner import run_container
# ══════════════════════════════════════════════════════════════════════════════

def run_container(image: str, env_overrides: dict):
    """
    Run a container from an image.

    Parameters:
        image         — "myapp:latest"
        env_overrides — extra env vars from -e flags, e.g. {"NAME": "World"}

    Returns:
        int — the container's exit code (0 = success)

    Raises:
        FileNotFoundError — if the image doesn't exist
        RuntimeError      — if container setup fails
    """
    # ── STUB — DELETE THIS BLOCK WHEN MEMBER 4 IS READY ──────────────────────
    print(f"  [STUB] Member 4 not integrated yet — would run '{image}'")
    print(f"  [STUB] Env overrides: {env_overrides}")
    return 0  # pretend success
    # ─────────────────────────────────────────────────────────────────────────
