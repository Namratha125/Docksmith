"""
cache.py — Build cache: key computation, hit/miss checks, and index management.

Member 2's job: Make caching correct and deterministic.

The cache index lives at: ~/.docksmith/cache/index.json
Format: { "<cache_key>": "<layer_digest>" }

Cache key inputs (per spec):
  - Previous layer digest (or base image manifest digest for the 1st layer step)
  - Full instruction text as written in Docksmithfile
  - Current WORKDIR value (empty string if not set)
  - All ENV vars accumulated so far, sorted lexicographically (empty string if none)
  - COPY only: SHA-256 of each source file, concatenated in sorted path order
"""

import hashlib
import json
import os
import glob


# ── Paths ──────────────────────────────────────────────────────────────────────

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
CACHE_DIR     = os.path.join(DOCKSMITH_DIR, "cache")
CACHE_INDEX   = os.path.join(CACHE_DIR, "index.json")
LAYERS_DIR    = os.path.join(DOCKSMITH_DIR, "layers")


# ── Cache index helpers ────────────────────────────────────────────────────────

def _load_index() -> dict:
    """Load the cache index from disk. Returns {} if it doesn't exist yet."""
    if not os.path.isfile(CACHE_INDEX):
        return {}
    with open(CACHE_INDEX, "r") as f:
        return json.load(f)


def _save_index(index: dict):
    """Save the cache index to disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_INDEX, "w") as f:
        json.dump(index, f, indent=2)


# ── File hashing ───────────────────────────────────────────────────────────────

def hash_file(path: str) -> str:
    """Return the SHA-256 hex digest of a single file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


# ── Source-file hashing for COPY ───────────────────────────────────────────────

def _expand_globs(src_pattern: str, context_path: str) -> list:
    """
    Expand a glob pattern relative to context_path.
    Returns a sorted list of matching absolute file paths.
    """
    full_pattern = os.path.join(context_path, src_pattern)
    matches = glob.glob(full_pattern, recursive=True)
    # Only include files, not directories
    files = [m for m in matches if os.path.isfile(m)]
    return sorted(files)


def hash_copy_sources(src_pattern: str, context_path: str) -> str:
    """
    For a COPY instruction, compute a combined hash of all source files.

    Per spec: SHA-256 of each source file's raw bytes,
    concatenated in lexicographically sorted path order.

    Returns a hex string to include in the cache key.
    """
    files = _expand_globs(src_pattern, context_path)

    if not files:
        # No files matched — return hash of empty string
        return hash_bytes(b"")

    combined = hashlib.sha256()
    for filepath in files:
        # Include the relative path so renames bust the cache
        rel = os.path.relpath(filepath, context_path)
        combined.update(rel.encode())
        combined.update(hash_file(filepath).encode())

    return combined.hexdigest()


# ── Cache key computation ──────────────────────────────────────────────────────

def compute_cache_key(
    prev_digest: str,
    instruction_raw: str,
    workdir: str,
    env_state: dict,
    copy_src_hash: str = "",   # only used for COPY
) -> str:
    """
    Compute the deterministic cache key for a COPY or RUN instruction.

    Inputs (all combined into one SHA-256):
      1. prev_digest      — digest of the previous layer (or base image manifest digest)
      2. instruction_raw  — full instruction text e.g. "COPY . /app"
      3. workdir          — current WORKDIR value (empty string if not set)
      4. env_state        — dict of all ENV vars set so far, sorted by key
      5. copy_src_hash    — hash of source files (only for COPY instructions)

    Returns: hex string (the cache key)
    """
    h = hashlib.sha256()

    # 1. Previous layer digest
    h.update(prev_digest.encode())

    # 2. Full instruction text
    h.update(instruction_raw.encode())

    # 3. WORKDIR value
    h.update(workdir.encode())

    # 4. ENV state — sorted by key for determinism
    env_sorted = sorted(env_state.items())   # list of (key, value) tuples
    env_string = "&".join(f"{k}={v}" for k, v in env_sorted)
    h.update(env_string.encode())

    # 5. COPY source file hash (empty string for RUN)
    h.update(copy_src_hash.encode())

    return h.hexdigest()


# ── Hit / miss logic ───────────────────────────────────────────────────────────

def lookup(cache_key: str) -> str | None:
    """
    Check if cache_key has a hit.

    Returns the layer digest if:
      - the key exists in the index AND
      - the layer tar file actually exists on disk (not just in index)

    Returns None on any miss.
    """
    index = _load_index()
    layer_digest = index.get(cache_key)

    if layer_digest is None:
        return None  # Key not in index

    # Also verify the layer file actually exists on disk
    layer_filename = layer_digest.replace("sha256:", "") + ".tar"
    layer_path = os.path.join(LAYERS_DIR, layer_filename)

    if not os.path.isfile(layer_path):
        return None  # Layer file missing → treat as miss

    return layer_digest


def store(cache_key: str, layer_digest: str):
    """
    Store a cache_key → layer_digest mapping in the index.
    Called after a CACHE MISS when we've written the new layer.
    """
    index = _load_index()
    index[cache_key] = layer_digest
    _save_index(index)
