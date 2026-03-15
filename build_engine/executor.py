"""
executor.py — Executes each Docksmithfile instruction during a build.
"""

import os
import json
import glob
import shutil
import hashlib
import tarfile
import tempfile
import subprocess
import time


DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR    = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR    = os.path.join(DOCKSMITH_DIR, "layers")

# Directories to always skip during COPY
SKIP_DIRS = {".git", "__pycache__", ".docksmith", "node_modules", ".venv", "venv"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ensure_dirs():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)


def _hash_tar(tar_path):
    h = hashlib.sha256()
    with open(tar_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _tar_filter(tarinfo):
    tarinfo.mtime = 0
    tarinfo.uid   = 0
    tarinfo.gid   = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    return tarinfo


def _write_layer(tmp_tar_path):
    _ensure_dirs()
    digest = _hash_tar(tmp_tar_path)
    size   = os.path.getsize(tmp_tar_path)
    hex_digest = digest.replace("sha256:", "")
    layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")
    if not os.path.isfile(layer_path):
        shutil.move(tmp_tar_path, layer_path)
    else:
        os.remove(tmp_tar_path)
    return digest, size


def _should_skip(rel_path):
    """Return True if any component of the path is in SKIP_DIRS."""
    parts = rel_path.replace("\\", "/").split("/")
    return any(p in SKIP_DIRS for p in parts)


def _collect_files(base_dir):
    """
    Walk base_dir and return sorted list of (rel_path, abs_path) for every file,
    automatically skipping SKIP_DIRS.
    """
    results = []
    for dirpath, dirnames, filenames in os.walk(base_dir):
        # Prune skip dirs so os.walk never descends into them
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fname in sorted(filenames):
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, base_dir)
            if not _should_skip(rel_path):
                results.append((rel_path, abs_path))
    return results


def _make_tar(delta_dir, tmp_tar_path):
    """Build a sorted, reproducible tar of delta_dir."""
    with tarfile.open(tmp_tar_path, "w") as tar:
        entries = []
        for dirpath, dirnames, filenames in os.walk(delta_dir):
            dirnames.sort()
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                arc  = os.path.relpath(full, delta_dir)
                entries.append((arc, full))
            for dname in sorted(dirnames):
                full = os.path.join(dirpath, dname)
                arc  = os.path.relpath(full, delta_dir)
                entries.append((arc, full))
        entries.sort(key=lambda x: x[0])
        for arc, full in entries:
            tar.add(full, arcname=arc, filter=_tar_filter)


# ── Load base image ────────────────────────────────────────────────────────────

def load_base_image(image_ref):
    _ensure_dirs()
    if ":" in image_ref:
        name, tag = image_ref.split(":", 1)
    else:
        name, tag = image_ref, "latest"
    manifest_path = os.path.join(IMAGES_DIR, f"{name}_{tag}.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            f"Base image '{image_ref}' not found in ~/.docksmith/images/. "
            f"Place {name}_{tag}.json there before building."
        )
    with open(manifest_path, "r") as f:
        return json.load(f)


# ── Assemble filesystem ────────────────────────────────────────────────────────

def assemble_filesystem(layer_digests, tmp_dir):
    for digest in layer_digests:
        hex_digest = digest.replace("sha256:", "")
        layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")
        if not os.path.isfile(layer_path):
            raise FileNotFoundError(f"Layer '{digest}' missing from disk.")
        with tarfile.open(layer_path, "r") as tar:
            tar.extractall(path=tmp_dir)


# ── COPY instruction ───────────────────────────────────────────────────────────

def execute_copy(src_pattern, dest, context_path, current_layers, workdir):
    _ensure_dirs()

    dest_clean = dest.lstrip("/").lstrip("\\")

    with tempfile.TemporaryDirectory() as delta_dir:

        src_abs = os.path.normpath(os.path.join(context_path, src_pattern))

        if os.path.isdir(src_abs):
            # Walk the directory ourselves — never use copytree (it copies .git)
            for rel_path, abs_path in _collect_files(src_abs):
                dst = os.path.join(delta_dir, dest_clean, rel_path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    shutil.copy2(abs_path, dst)
                except (PermissionError, OSError):
                    pass  # skip locked files silently

        elif os.path.isfile(src_abs):
            fname = os.path.basename(src_abs)
            dst   = os.path.join(delta_dir, dest_clean, fname)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src_abs, dst)

        else:
            # Glob pattern
            matches = sorted(glob.glob(
                os.path.join(context_path, src_pattern), recursive=True
            ))
            matches = [m for m in matches
                       if not _should_skip(os.path.relpath(m, context_path))]
            if not matches:
                raise FileNotFoundError(
                    f"COPY: no files matched '{src_pattern}' in '{context_path}'"
                )
            for src_path in matches:
                if os.path.isfile(src_path):
                    rel = os.path.relpath(src_path, context_path)
                    dst = os.path.join(delta_dir, dest_clean, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    try:
                        shutil.copy2(src_path, dst)
                    except (PermissionError, OSError):
                        pass

        # Ensure WORKDIR exists in delta
        if workdir:
            os.makedirs(
                os.path.join(delta_dir, workdir.lstrip("/").lstrip("\\")),
                exist_ok=True
            )

        tmp_tar_fd, tmp_tar_path = tempfile.mkstemp(suffix=".tar")
        os.close(tmp_tar_fd)
        try:
            _make_tar(delta_dir, tmp_tar_path)
            return _write_layer(tmp_tar_path)
        except Exception:
            if os.path.isfile(tmp_tar_path):
                os.remove(tmp_tar_path)
            raise


# ── RUN instruction ────────────────────────────────────────────────────────────

def execute_run(command, current_layers, workdir, env_state):
    _ensure_dirs()

    with tempfile.TemporaryDirectory() as chroot_root:
        assemble_filesystem(current_layers, chroot_root)

        if workdir:
            os.makedirs(
                os.path.join(chroot_root, workdir.lstrip("/").lstrip("\\")),
                exist_ok=True
            )

        before_snapshot = _snapshot(chroot_root)
        _run_in_chroot(command, chroot_root, workdir, env_state)
        after_snapshot  = _snapshot(chroot_root)
        changed_files   = _diff_snapshots(before_snapshot, after_snapshot)

        tmp_tar_fd, tmp_tar_path = tempfile.mkstemp(suffix=".tar")
        os.close(tmp_tar_fd)
        try:
            with tarfile.open(tmp_tar_path, "w") as tar:
                for rel_path in sorted(changed_files):
                    full = os.path.join(chroot_root, rel_path)
                    if os.path.exists(full):
                        tar.add(full, arcname=rel_path, filter=_tar_filter)
            return _write_layer(tmp_tar_path)
        except Exception:
            if os.path.isfile(tmp_tar_path):
                os.remove(tmp_tar_path)
            raise


def _run_in_chroot(command, chroot_root, workdir, env):
    import platform
    if platform.system() == "Windows":
        print(f"  [Windows] RUN skipped (needs Linux): {command}")
        return
    env_exports = " ".join(f'export {k}="{v}";' for k, v in env.items())
    working_dir = workdir if workdir else "/"
    script = (
        f"chroot {chroot_root} /bin/sh -c '"
        f"cd {working_dir} 2>/dev/null || cd /; "
        f"{env_exports} "
        f"{command}'"
    )
    result = subprocess.run(
        ["unshare", "--mount", "--pid", "--fork", "sh", "-c", script],
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"RUN failed (exit {result.returncode}): {command}")


def _snapshot(root):
    snapshot = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel  = os.path.relpath(full, root)
            try:
                stat = os.stat(full)
                snapshot[rel] = (stat.st_mtime, stat.st_size)
            except OSError:
                pass
    return snapshot


def _diff_snapshots(before, after):
    changed = []
    for rel_path, (mt_after, sz_after) in after.items():
        if rel_path not in before:
            changed.append(rel_path)
        else:
            mt_before, sz_before = before[rel_path]
            if mt_after != mt_before or sz_after != sz_before:
                changed.append(rel_path)
    return changed