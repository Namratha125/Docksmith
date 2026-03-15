"""
builder.py — Main entry point for the Build Engine.

Member 2's job: Orchestrate the entire build process.

This is the function that Member 1's CLI calls via interfaces.py:
    from build_engine.builder import build_image

Flow:
  1. Parse the Docksmithfile (parser.py)
  2. For each instruction:
     a. FROM   → load base image, set prev_digest
     b. WORKDIR/ENV/CMD → update build state, no layer
     c. COPY/RUN → compute cache key, check cache, execute if miss, store result
  3. Write the final image manifest to ~/.docksmith/images/
  4. Return the result dict that CLI's commands.py expects
"""

import os
import json
import hashlib
import datetime
import time

from build_engine import parser, cache, executor


DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR    = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR    = os.path.join(DOCKSMITH_DIR, "layers")


# ── Main entry point ───────────────────────────────────────────────────────────

def build_image(tag: str, context_path: str, no_cache: bool = False) -> dict:
    """
    Build an image from the Docksmithfile in context_path.

    Parameters:
        tag          — "myapp:latest"
        context_path — path to directory containing Docksmithfile
        no_cache     — if True, skip all cache lookups (still write layers)

    Returns:
        {
            "steps": [
                {"instruction": "FROM alpine:3.18", "cache_hit": False, "duration": 0.0},
                {"instruction": "COPY . /app",      "cache_hit": True,  "duration": 0.01},
                ...
            ],
            "image_digest": "sha256:a3f9b2c1..."
        }

    Raises:
        FileNotFoundError — Docksmithfile not found / base image missing
        SyntaxError       — bad Docksmithfile instruction
        RuntimeError      — RUN command failed
    """
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)

    # ── Parse the Docksmithfile ────────────────────────────────────────────────
    instructions = parser.parse(context_path)

    # ── Split tag into name and tag parts ──────────────────────────────────────
    if ":" in tag:
        image_name, image_tag = tag.split(":", 1)
    else:
        image_name, image_tag = tag, "latest"

    # ── Build state ────────────────────────────────────────────────────────────
    current_layers = []      # list of layer digests accumulated so far
    prev_digest    = ""      # digest of the previous COPY/RUN layer (or base image manifest)
    workdir        = ""      # current WORKDIR value
    env_state      = {}      # accumulated ENV vars
    cmd            = []      # CMD for the final image

    # Results for CLI
    steps          = []
    cascade_miss   = False   # once True, all remaining steps are misses

    # Count total steps for "Step N/M" display
    total_steps = len(instructions)

    # ── Process each instruction ───────────────────────────────────────────────
    for step_index, instr in enumerate(instructions, start=1):
        keyword = instr["instruction"]
        args    = instr["args"]
        raw     = instr["raw"]

        # ── FROM ───────────────────────────────────────────────────────────────
        if keyword == "FROM":
            manifest = executor.load_base_image(args)

            # Inherit base image layers
            for layer_entry in manifest.get("layers", []):
                current_layers.append(layer_entry["digest"])

            # Use the base image's manifest digest as the starting prev_digest
            # so that changing FROM busts all downstream cache entries
            prev_digest = manifest.get("digest", "")

            # Inherit base image config (env, workdir, cmd) as defaults
            base_config = manifest.get("config", {})
            for env_pair in base_config.get("Env", []):
                if "=" in env_pair:
                    k, _, v = env_pair.partition("=")
                    env_state[k] = v
            if base_config.get("WorkingDir"):
                workdir = base_config["WorkingDir"]

            # FROM never shows cache status or timing — just the step line
            steps.append({
                "instruction": raw,
                "cache_hit":   None,    # None = don't print cache status for FROM
                "duration":    None,
            })
            continue

        # ── WORKDIR ────────────────────────────────────────────────────────────
        elif keyword == "WORKDIR":
            workdir = args
            steps.append({
                "instruction": raw,
                "cache_hit":   None,
                "duration":    None,
            })
            continue

        # ── ENV ────────────────────────────────────────────────────────────────
        elif keyword == "ENV":
            # Support both KEY=VALUE and KEY VALUE syntax
            if "=" in args:
                k, _, v = args.partition("=")
                env_state[k.strip()] = v.strip()
            else:
                parts = args.split(None, 1)
                if len(parts) == 2:
                    env_state[parts[0]] = parts[1]
            steps.append({
                "instruction": raw,
                "cache_hit":   None,
                "duration":    None,
            })
            continue

        # ── CMD ────────────────────────────────────────────────────────────────
        elif keyword == "CMD":
            try:
                cmd = json.loads(args)
            except json.JSONDecodeError:
                raise SyntaxError(
                    f"CMD must be a JSON array, e.g. [\"python\",\"main.py\"]. Got: {args}"
                )
            steps.append({
                "instruction": raw,
                "cache_hit":   None,
                "duration":    None,
            })
            continue

        # ── COPY or RUN (layer-producing instructions) ─────────────────────────
        elif keyword in ("COPY", "RUN"):
            start_time = time.time()
            hit        = False

            # Compute cache key
            copy_src_hash = ""
            if keyword == "COPY":
                src_pattern = args.split()[0]
                copy_src_hash = cache.hash_copy_sources(src_pattern, context_path)

            cache_key = cache.compute_cache_key(
                prev_digest=prev_digest,
                instruction_raw=raw,
                workdir=workdir,
                env_state=env_state,
                copy_src_hash=copy_src_hash,
            )

            # Check cache (skip if --no-cache or cascading miss)
            cached_digest = None
            if not no_cache and not cascade_miss:
                cached_digest = cache.lookup(cache_key)

            if cached_digest is not None:
                # ── CACHE HIT ──────────────────────────────────────────────────
                hit           = True
                layer_digest  = cached_digest
                layer_size    = _get_layer_size(layer_digest)

            else:
                # ── CACHE MISS ─────────────────────────────────────────────────
                hit          = False
                cascade_miss = True   # all subsequent steps are also misses

                if keyword == "COPY":
                    src, dest = _parse_copy_args(args)
                    layer_digest, layer_size = executor.execute_copy(
                        src_pattern=src,
                        dest=dest,
                        context_path=context_path,
                        current_layers=current_layers,
                        workdir=workdir,
                    )
                else:  # RUN
                    layer_digest, layer_size = executor.execute_run(
                        command=args,
                        current_layers=current_layers,
                        workdir=workdir,
                        env_state=env_state,
                    )

                # Store in cache index (unless --no-cache)
                if not no_cache:
                    cache.store(cache_key, layer_digest)

            # Update build state
            current_layers.append(layer_digest)
            prev_digest = layer_digest

            duration = time.time() - start_time

            steps.append({
                "instruction": raw,
                "cache_hit":   hit,
                "duration":    round(duration, 2),
                "layer_digest": layer_digest,
                "layer_size":   layer_size,
                "created_by":   raw,
            })

    # ── Write image manifest ───────────────────────────────────────────────────
    manifest_path = os.path.join(IMAGES_DIR, f"{image_name}_{image_tag}.json")

    # If all steps were cache hits, preserve the original created timestamp
    # so the manifest digest is identical across rebuilds (per spec)
    original_created = None
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                old = json.load(f)
            original_created = old.get("created")
        except Exception:
            pass

    all_cache_hits = all(
        s["cache_hit"] is True
        for s in steps
        if s["cache_hit"] is not None   # skip FROM/WORKDIR/ENV/CMD
    )

    created_ts = original_created if (all_cache_hits and original_created) \
                 else datetime.datetime.utcnow().isoformat() + "Z"

    # Build layer list for manifest
    layer_entries = []
    for s in steps:
        if "layer_digest" in s:
            layer_entries.append({
                "digest":    s["layer_digest"],
                "size":      s.get("layer_size", 0),
                "createdBy": s.get("created_by", ""),
            })

    # Also include base image layers (from FROM)
    # We need to re-load base layers for the manifest
    base_layers = _get_base_layers(instructions)
    all_layer_entries = base_layers + layer_entries

    # Compute manifest digest: serialize with digest="" then SHA-256
    manifest_data = {
        "name":    image_name,
        "tag":     image_tag,
        "digest":  "",           # placeholder for digest computation
        "created": created_ts,
        "config": {
            "Env":        [f"{k}={v}" for k, v in sorted(env_state.items())],
            "Cmd":        cmd,
            "WorkingDir": workdir,
        },
        "layers": all_layer_entries,
    }

    canonical = json.dumps(manifest_data, separators=(",", ":"), sort_keys=True)
    manifest_digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    manifest_data["digest"] = manifest_digest

    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)

    # ── Build the return dict for Member 1's CLI ───────────────────────────────
    cli_steps = []
    for s in steps:
        cli_steps.append({
            "instruction": s["instruction"],
            "cache_hit":   s["cache_hit"],    # None for FROM/WORKDIR/ENV/CMD
            "duration":    s.get("duration"),
        })

    return {
        "steps":        cli_steps,
        "image_digest": manifest_digest,
    }


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_copy_args(args: str) -> tuple:
    """
    Parse COPY instruction args into (src_pattern, dest).
    Example: ". /app" → (".", "/app")
    """
    parts = args.split()
    if len(parts) < 2:
        raise SyntaxError(f"COPY requires <src> <dest>, got: {args}")
    src  = " ".join(parts[:-1])
    dest = parts[-1]
    return src, dest


def _get_layer_size(layer_digest: str) -> int:
    """Return the byte size of a layer tar file, or 0 if not found."""
    hex_digest = layer_digest.replace("sha256:", "")
    layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")
    if os.path.isfile(layer_path):
        return os.path.getsize(layer_path)
    return 0


def _get_base_layers(instructions: list) -> list:
    """
    Re-load the base image layers for inclusion in the manifest.
    """
    base_layers = []
    for instr in instructions:
        if instr["instruction"] == "FROM":
            try:
                manifest = executor.load_base_image(instr["args"])
                for layer in manifest.get("layers", []):
                    base_layers.append(layer)
            except Exception:
                pass
            break   # only one FROM supported
    return base_layers
