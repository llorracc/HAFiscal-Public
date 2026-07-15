#!/usr/bin/env python3
"""HAFiscal run-provenance emitter — unified sidecar + manifest + registry.

The single shared entry point that makes every result file traceable back to
the run that produced it. It UNIFIES the repo's existing provenance machinery
rather than adding a fourth competing one:

- reuses ``reproduce/build_manifest.py`` capture helpers (HARK state, pip-freeze)
  for the heavy central manifest,
- reuses ``_registry.py`` for the run_id and the queryable SQLite archive,
- reads the *resolved effective config* via ``config.effective_config()`` (the
  world / method / interpretation actually in force) instead of a raw env dump,
- and adds the one genuinely new artifact: a small, travelling sibling
  ``RUN_<run_id>.prov.json`` written next to a run's outputs, back-referencing
  the central manifest by ``run_id``.

Design plan: "Unified Run Provenance and Discoverable Sidecars"
(see CLAUDE.md Documentation Map).

Hard constraints (by design):
- NEVER writes provenance into a result file's bytes. A ``# run_id`` header
  would change the file's sha256 (breaking LOCKED_TABLES.manifest +
  test_locked_tables) and pollute the two-machine byte-level comparison.
  Provenance is ALWAYS a separate sibling file.
- NEVER uses symlinks next to results (they dangle when results are copied
  across machines / tarred without -h).
- Best-effort: a provenance failure must NEVER abort the underlying run. The
  importable API swallows and warns; only the CLI may exit non-zero.
- NO retroactive backfill of frozen deliverables. Emitting a sidecar NOW next to
  a QE-frozen result would stamp it with today's commit/dirty state — a false
  claim that the current tree produced the published numbers. Provenance is
  captured forward, at the run that produces a file; frozen-result provenance is
  the published commit / frozen tag (see CLAUDE.md), not a backfilled sidecar.

Importable API
--------------
    import provenance
    info = provenance.emit(["Results"], command="...", output_roots=[...])
    # -> {"run_id", "sidecars", "manifest", "registry_run_id", "errors"}

CLI (for bash callers)
----------------------
    python provenance.py emit --output-dir Results [--output-dir DIR ...] \
        [--command STR] [--label STR] [--output-root REL ...] \
        [--no-register] [--no-central] [--manifest PATH]
    python provenance.py show <result-file-or-dir>
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

SCHEMA_VERSION = "1"
SIDECAR_PREFIX = "RUN_"
SIDECAR_SUFFIX = ".prov.json"

_HA_ROOT = Path(__file__).resolve().parent              # Code/HA-Models
_REPO_ROOT = _HA_ROOT.parent.parent                     # repo root
_DEFAULT_MANIFEST_DIR = _REPO_ROOT / "reproduce" / "run-manifests"

# Thread-count env that is "wrapper env" set in the shell, invisible to argv.
_THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


# ---------------------------------------------------------------------------
# Lazy, best-effort imports of the existing machinery (never hard-fail)
# ---------------------------------------------------------------------------

def _load_build_manifest():
    try:
        rp = str(_REPO_ROOT / "reproduce")
        if rp not in sys.path:
            sys.path.insert(0, rp)
        import build_manifest  # type: ignore
        return build_manifest
    except Exception:
        return None


def _load_config():
    try:
        if str(_HA_ROOT) not in sys.path:
            sys.path.insert(0, str(_HA_ROOT))
        import config  # type: ignore
        return config
    except Exception:
        return None


def _load_registry():
    try:
        if str(_HA_ROOT) not in sys.path:
            sys.path.insert(0, str(_HA_ROOT))
        import _registry  # type: ignore
        return _registry
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(*args: str, cwd: Optional[Path] = None) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=str(cwd or _REPO_ROOT), stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return ""


def _git_dirty() -> bool:
    return bool(_git("status", "--porcelain"))


def _git_diff_sha256() -> Optional[str]:
    """sha256 of the tracked diff vs HEAD; None if clean/unavailable.

    A commit hash on a dirty tree points at code that never existed, so we
    fingerprint the working-tree delta to disambiguate.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "HEAD"], cwd=str(_REPO_ROOT), stderr=subprocess.DEVNULL
        )
    except Exception:
        return None
    if not out:
        return None
    return hashlib.sha256(out).hexdigest()


def _sha256_file(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _repo_rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(_REPO_ROOT))
    except ValueError:
        return str(Path(p).resolve())


def _wrapper_env() -> dict:
    """Snapshot ALL HAFISCAL_* env vars plus BLAS thread counts.

    Captures what raw-argv misses: env exported in the launching shell
    (e.g. HAFISCAL_NUM_STARTS, OMP_NUM_THREADS).
    """
    env = {k: v for k, v in os.environ.items() if k.startswith("HAFISCAL_")}
    for k in _THREAD_ENV:
        if k in os.environ:
            env[k] = os.environ[k]
    return dict(sorted(env.items()))


_ENV_FLAG_REGISTRY = _HA_ROOT / "docs" / "ENV_FLAGS.md"
_FLAG_HEADING_RE = re.compile(r"^### (HAFISCAL_[A-Z0-9_]+)\s*$", re.MULTILINE)


def _known_flag_names() -> list:
    """All HAFISCAL_* flag names from the authoritative ENV_FLAGS.md registry.

    Returns [] if the registry is unavailable (minimal checkout)."""
    try:
        text = _ENV_FLAG_REGISTRY.read_text()
    except Exception:
        return []
    return sorted(set(_FLAG_HEADING_RE.findall(text)))


def _full_env_capture() -> tuple:
    """Capture the effective flag surface against the ENV_FLAGS.md registry.

    Returns (set_flags, registry_meta) where:
    - set_flags     : {flag: value} for ONLY the registry flags that are SET.
      Unset flags are omitted (they take their code default at `git_commit`,
      resolvable via the pinned registry). Reproduction = set these values,
      checkout the commit, done.
    - registry_meta : {path, sha256, flag_count, flags_set, flags_unset} so a
      reader knows the full surface size and can resolve the omitted flags'
      documented defaults at the recorded commit.
    """
    flags = _known_flag_names()
    set_flags = {f: os.environ[f] for f in flags if f in os.environ}
    meta = {
        "path": _repo_rel(_ENV_FLAG_REGISTRY) if _ENV_FLAG_REGISTRY.exists() else None,
        "sha256": _sha256_file(_ENV_FLAG_REGISTRY) if _ENV_FLAG_REGISTRY.exists() else None,
        "flag_count": len(flags),
        "flags_set": len(set_flags),
        "flags_unset": len(flags) - len(set_flags),
    }
    return set_flags, meta


# ---------------------------------------------------------------------------
# Resolved effective config + run_id
# ---------------------------------------------------------------------------

def effective_config() -> dict:
    """The resolved effective config (world/method/interpretation + env map)."""
    cfg = _load_config()
    if cfg is not None and hasattr(cfg, "effective_config"):
        try:
            return cfg.effective_config()
        except Exception as e:  # pragma: no cover - defensive
            return {"error": f"config.effective_config failed: {e}"}
    return {
        "world": os.environ.get("HAFISCAL_WORLD", "default"),
        "method": (os.environ.get("HAFISCAL_SIM_METHOD")
                   or os.environ.get("HAFISCAL_MULTIPLIER_ENGINE")),
        "interpretation": os.environ.get("HAFISCAL_INTERPRETATION", "ESC"),
        "perm_during_unemp": os.environ.get("HAFISCAL_PERM_DURING_UNEMP"),
        "unavailable": True,
    }


def make_run_id() -> str:
    """`<commit8>_<confighash6>_<date>` (via _registry), with a git-only fallback."""
    reg = _load_registry()
    if reg is not None:
        try:
            return reg.make_run_id()
        except Exception:
            pass
    commit = _git("rev-parse", "--short=8", "HEAD") or "nogit000"
    return f"{commit}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"


# ---------------------------------------------------------------------------
# Sidecar
# ---------------------------------------------------------------------------

def gather(
    *,
    command: Optional[str] = None,
    argv: Optional[Iterable[str]] = None,
    run_id: Optional[str] = None,
    manifest_ref: Optional[str] = None,
    registry_run_id: Optional[str] = None,
    label: Optional[str] = None,
    extra: Optional[dict] = None,
    overrides: Optional[dict] = None,
) -> dict:
    """Build the small sidecar dict (the travelling provenance record).

    ``overrides``: optional dict merged over the captured fields LAST. Used by the
    `reconstruct` path to pin a run's real historical facts (commit, time, env)
    and stamp ``reconstructed``/``reconstructed_from`` — never fabricate facts.
    """
    if run_id is None:
        run_id = make_run_id()
    argv_list = list(argv) if argv else []
    if command is None:
        command = " ".join(argv_list)
    set_flags, env_flags_registry = _full_env_capture()
    sidecar = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_utc": _now_iso(),
        "label": label,
        "host": socket.gethostname(),
        "user": getpass.getuser(),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": _git_dirty(),
        "git_diff_sha256": _git_diff_sha256(),
        "command_line": command,
        "argv": argv_list,
        "wrapper_env": _wrapper_env(),
        "set_flags": set_flags,
        "env_flags_registry": env_flags_registry,
        "resolved_config": effective_config(),
        "manifest_ref": manifest_ref,
        "registry_run_id": registry_run_id,
    }
    if extra:
        sidecar["extra"] = extra
    if overrides:
        sidecar.update(overrides)
    return sidecar


def sidecar_name(run_id: str) -> str:
    return f"{SIDECAR_PREFIX}{run_id}{SIDECAR_SUFFIX}"


def write_sidecar(output_dir, sidecar: dict) -> Path:
    """Atomically write RUN_<run_id>.prov.json into output_dir. Returns its path."""
    d = Path(output_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / sidecar_name(sidecar["run_id"])
    tmp = d / f".{path.name}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(sidecar, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)  # POSIX-atomic
    return path


# ---------------------------------------------------------------------------
# Central manifest (heavy record; reuses build_manifest capture helpers)
# ---------------------------------------------------------------------------

def _hash_outputs(roots: Iterable[str]) -> dict:
    """Hash files under each root (or single files). Skips our own sidecars,
    dotfiles, __pycache__, and *.tmp scratch."""
    out: dict = {}
    for root_str in roots or ():
        # Resolve relative to CWD (consistent with write_sidecar / --output-dir);
        # stored back as repo-relative when possible.
        p = Path(root_str).resolve()
        if not p.exists():
            continue
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file())
        for q in files:
            rel_parts = q.relative_to(_REPO_ROOT).parts if str(q).startswith(str(_REPO_ROOT)) else q.parts
            if any(part.startswith(".") or part == "__pycache__" for part in rel_parts):
                continue
            if q.name.endswith(SIDECAR_SUFFIX) or q.name.endswith(".tmp"):
                continue
            try:
                st = q.stat()
                out[_repo_rel(q)] = {
                    "sha256": _sha256_file(q),
                    "bytes": st.st_size,
                    "mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            except OSError:
                continue
    return out


def write_central_manifest(path, sidecar: dict, output_roots: Iterable[str] = ()) -> Path:
    """Write the heavy run manifest JSON, reusing build_manifest helpers."""
    bm = _load_build_manifest()
    path = Path(path)
    pip_rel = pip_sha = None
    hark = {"hark_version": None, "hark_install_path": None, "hark_git_commit": None}
    if bm is not None:
        try:
            hark = bm._hark_state()
        except Exception:
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pip_rel, pip_sha = bm._capture_pip_freeze(
                path.with_name(path.stem + "_pip_freeze.txt")
            )
        except Exception:
            pass

    uv_lock = _REPO_ROOT / "uv.lock"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "run-provenance",
        "run_id": sidecar.get("run_id"),
        "registry_run_id": sidecar.get("registry_run_id"),
        "invocation": {
            "command_line": sidecar.get("command_line"),
            "argv": sidecar.get("argv"),
            "label": sidecar.get("label"),
            "started_at_utc": sidecar.get("created_utc"),
            "user": sidecar.get("user"),
            "hostname": sidecar.get("host"),
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "platform_release": platform.release(),
            "wrapper_env": sidecar.get("wrapper_env"),
            "set_flags": sidecar.get("set_flags"),
            "env_flags_registry": sidecar.get("env_flags_registry"),
        },
        "code_state": {
            "branch": sidecar.get("branch"),
            "git_commit": sidecar.get("git_commit"),
            "git_dirty": sidecar.get("git_dirty"),
            "git_diff_sha256": sidecar.get("git_diff_sha256"),
            "hark_version": hark.get("hark_version"),
            "hark_install_path": hark.get("hark_install_path"),
            "hark_git_commit": hark.get("hark_git_commit"),
            "python_version": platform.python_version(),
        },
        "environment_lock": {
            "pip_freeze_path": pip_rel,
            "pip_freeze_sha256": pip_sha,
            "uv_lockfile_sha256": _sha256_file(uv_lock) if uv_lock.exists() else None,
        },
        "resolved_config": sidecar.get("resolved_config"),
        "outputs": _hash_outputs(output_roots),
    }
    # Carry reconstruction markers (if this is an after-the-fact reconstruction)
    # so the heavy record is just as honest as the sidecar.
    for _k in ("reconstructed", "reconstructed_from", "reconstructed_note"):
        if sidecar.get(_k) is not None:
            manifest[_k] = sidecar[_k]

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)
    return path


def _register_run(run_id: str) -> Optional[str]:
    reg = _load_registry()
    if reg is None:
        return None
    try:
        cfg = reg.get_current_config()
        return reg.register_run(cfg, run_id=run_id, notes="provenance.emit")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# The one public entry point used by every caller
# ---------------------------------------------------------------------------

def emit(
    output_dirs: Iterable[str],
    *,
    command: Optional[str] = None,
    argv: Optional[Iterable[str]] = None,
    label: Optional[str] = None,
    register: bool = True,
    central: bool = True,
    manifest_path=None,
    manifest_ref: Optional[str] = None,
    output_roots: Optional[Iterable[str]] = None,
    run_id: Optional[str] = None,
    overrides: Optional[dict] = None,
    verbose: bool = True,
) -> dict:
    """Emit provenance for a run: register (registry) + central manifest +
    a sibling sidecar in each of ``output_dirs``.

    ``output_dirs`` : directories to drop a ``RUN_<run_id>.prov.json`` into.
    ``output_roots``: files/dirs to hash into the central manifest
                      (defaults to ``output_dirs``).
    ``manifest_ref``: if given, the sidecar points at this EXISTING manifest and
                      NO competing central manifest is written (for callers like
                      reproduce.sh that already build their own manifest).

    Never raises. Returns a dict with run_id, sidecars, manifest, registry_run_id,
    and any non-fatal errors.
    """
    result = {"run_id": None, "sidecars": [], "manifest": None,
              "registry_run_id": None, "errors": []}
    try:
        # Only drop sidecars into dirs that already exist (don't fabricate
        # output dirs for steps that never ran / produced nothing).
        output_dirs = [d for d in output_dirs if Path(d).is_dir()]
        if run_id is None:
            run_id = make_run_id()
        registry_run_id = _register_run(run_id) if register else None

        # An explicit manifest_ref means: reuse the caller's manifest, don't write one.
        if manifest_ref is not None:
            central = False

        manifest_written = None
        if central:
            # `provrun_` prefix distinguishes ad-hoc provenance manifests (gitignored)
            # from reproduce.sh's tracked `comp_*.json` manifests in the same dir.
            mpath = Path(manifest_path) if manifest_path else (_DEFAULT_MANIFEST_DIR / f"provrun_{run_id}.json")
            sc_pre = gather(command=command, argv=argv, run_id=run_id,
                            registry_run_id=registry_run_id, label=label,
                            overrides=overrides)
            try:
                manifest_written = write_central_manifest(
                    mpath, sc_pre, output_roots if output_roots is not None else output_dirs)
                manifest_ref = _repo_rel(manifest_written)
            except Exception as e:  # pragma: no cover - defensive
                result["errors"].append(f"central manifest: {e}")

        sidecar = gather(command=command, argv=argv, run_id=run_id,
                         manifest_ref=manifest_ref, registry_run_id=registry_run_id,
                         label=label, overrides=overrides)
        for d in output_dirs:
            try:
                p = write_sidecar(d, sidecar)
                result["sidecars"].append(str(p))
            except Exception as e:
                result["errors"].append(f"sidecar {d}: {e}")

        result["run_id"] = run_id
        result["registry_run_id"] = registry_run_id
        result["manifest"] = str(manifest_written) if manifest_written else None

        if verbose:
            print(f"[provenance] run_id={run_id}  sidecars={len(result['sidecars'])}  "
                  f"manifest={'ok' if manifest_written else 'skip'}  "
                  f"registry={'ok' if registry_run_id else 'skip'}")
            for e in result["errors"]:
                print(f"[provenance] WARNING: {e}", file=sys.stderr)
    except Exception as e:  # pragma: no cover - never abort the run
        print(f"[provenance] WARNING: emit failed (non-fatal): {e}", file=sys.stderr)
        result["errors"].append(str(e))
    return result


# ---------------------------------------------------------------------------
# Reverse lookup (discoverability) — `provenance show <file-or-dir>`
# ---------------------------------------------------------------------------

def find_sidecars(target) -> list:
    """Return sidecar paths relevant to a result file or directory.

    For a file: sidecars in its parent dir. For a dir: sidecars in that dir.
    """
    t = Path(target).resolve()
    d = t if t.is_dir() else t.parent
    if not d.exists():
        return []
    return sorted(d.glob(f"{SIDECAR_PREFIX}*{SIDECAR_SUFFIX}"))


def load_sidecar(path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_emit(args: argparse.Namespace) -> int:
    info = emit(
        args.output_dir,
        command=args.command,
        argv=args.argv.split() if args.argv else None,
        label=args.label,
        register=not args.no_register,
        central=not args.no_central,
        manifest_path=args.manifest,
        manifest_ref=args.manifest_ref,
        output_roots=args.output_root or None,
        verbose=True,
    )
    return 0 if not info["errors"] else 0  # non-fatal: always succeed


def _cmd_reconstruct(args: argparse.Namespace) -> int:
    """Emit a CLEARLY-MARKED after-the-fact provenance record for a past run.

    Only legitimate when the run's real facts come from an authoritative source
    (a run log). Pins the run's actual commit / time / env and stamps
    `reconstructed: true` + `reconstructed_from`; never fabricates facts. Fields
    that are genuinely unrecoverable (working-tree dirtiness, diff sha) are set
    to null rather than guessed. Does NOT touch the registry (its timestamps
    would be 'now', not the run's)."""
    wrapper_env = {}
    for kv in args.wrapper_env or []:
        if "=" in kv:
            k, v = kv.split("=", 1)
            wrapper_env[k] = v
    # Apply the run's env to THIS process so resolved_config + all_known_flags
    # reflect the run's config, not the reconstructing shell.
    for k, v in wrapper_env.items():
        if k.startswith("HAFISCAL_") or k in _THREAD_ENV:
            os.environ[k] = v
    # Also apply the resolved world's catalog defaults via setdefault (explicit
    # wrapper_env still wins), so the run's effective canonical flags (perm,
    # shuffle, aMax, UI encoding, ...) are reflected — not left falsely "unset".
    if not args.no_resolve_world:
        cfg = _load_config()
        if cfg is not None:
            try:
                world = os.environ.get("HAFISCAL_WORLD", "default")
                for k, v in cfg.resolve_world(world).items():
                    os.environ.setdefault(k, v)
            except Exception:
                pass
    overrides = {
        "reconstructed": True,
        "reconstructed_from": args.reconstructed_from,
        "reconstructed_note": args.note,
        "git_dirty": None,         # unknown at reconstruction time
        "git_diff_sha256": None,   # unrecoverable
    }
    if args.created_utc:
        overrides["created_utc"] = args.created_utc
    if args.git_commit:
        overrides["git_commit"] = args.git_commit
    if args.branch:
        overrides["branch"] = args.branch
    if wrapper_env:
        overrides["wrapper_env"] = dict(sorted(wrapper_env.items()))

    info = emit(
        args.output_dir,
        command=args.command,
        label=args.label,
        register=False,           # registry timestamps would be 'now', not the run's
        central=not args.no_central,
        manifest_path=args.manifest,
        output_roots=args.output_root or None,
        run_id=args.run_id,
        overrides=overrides,
        verbose=True,
    )
    if info["run_id"]:
        print(f"[provenance] reconstructed record for run_id={info['run_id']} "
              f"(marked reconstructed; source: {args.reconstructed_from})")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    sidecars = find_sidecars(args.target)
    if not sidecars:
        print(f"[provenance] no sidecar found next to {args.target}")
        print("  (this result predates provenance capture, or was produced by an "
              "entry point not yet wired)")
        return 1
    print(f"provenance for : {args.target}")
    print(f"(the result file's bytes are untouched; provenance lives in the "
          f"sibling JSON file{'s' if len(sidecars) > 1 else ''} below)")
    for sc_path in sidecars:
        try:
            sc = load_sidecar(sc_path)
        except Exception as e:
            print(f"[provenance] cannot read {sc_path}: {e}", file=sys.stderr)
            continue
        rc = sc.get("resolved_config", {}) or {}
        print("=" * 72)
        if sc.get("reconstructed"):
            print("*** RECONSTRUCTED after the fact (not a live capture) ***")
            print(f"    source: {sc.get('reconstructed_from')}")
            if sc.get("reconstructed_note"):
                print(f"    note  : {sc.get('reconstructed_note')}")
        print(f"sidecar : {_repo_rel(sc_path)}")
        print(f"run_id  : {sc.get('run_id')}")
        print(f"created : {sc.get('created_utc')}  by {sc.get('user')}@{sc.get('host')}")
        print(f"branch  : {sc.get('branch')}  commit {str(sc.get('git_commit'))[:12]}"
              f"  dirty={sc.get('git_dirty')}"
              + (f"  diff_sha={str(sc.get('git_diff_sha256'))[:12]}" if sc.get('git_diff_sha256') else ""))
        print(f"config  : world={rc.get('world')} method={rc.get('method')} "
              f"interp={rc.get('interpretation')} perm={rc.get('perm_during_unemp')}")
        print(f"command : {sc.get('command_line')}")
        reg = sc.get("env_flags_registry") or {}
        set_flags = sc.get("set_flags")
        if set_flags is not None and reg:
            print(f"flags   : {reg.get('flags_set', len(set_flags))}/{reg.get('flag_count', '?')} "
                  f"known HAFISCAL_* flags set "
                  f"(registry {str(reg.get('sha256'))[:12]} @ {reg.get('path')}); "
                  f"the other {reg.get('flags_unset', '?')} unset -> code default at this commit.")
            if set_flags:
                print("  set flags (the values to set when reproducing):")
                for k in sorted(set_flags):
                    print(f"    {k}={set_flags[k]}")
        else:
            we = sc.get("wrapper_env", {}) or {}
            shown = {k: we[k] for k in sorted(we) if k.startswith("HAFISCAL_")}
            print(f"env     : {', '.join(f'{k}={v}' for k, v in shown.items()) or '(none)'}")
        if sc.get("manifest_ref"):
            print(f"manifest: {sc.get('manifest_ref')}")
            mpath = _REPO_ROOT / sc["manifest_ref"]
            if mpath.exists():
                try:
                    man = json.loads(mpath.read_text())
                    outs = man.get("outputs", {}) or {}
                    if outs:
                        print(f"outputs recorded in manifest ({len(outs)}):")
                        for k, v in list(outs.items())[:20]:
                            print(f"    {k}  sha256:{str(v.get('sha256'))[:12]}  {v.get('bytes')}B")
                        if len(outs) > 20:
                            print(f"    ... and {len(outs) - 20} more")
                except Exception:
                    pass
            else:
                print("           (manifest file not found locally — may live on another machine)")
        if sc.get("registry_run_id"):
            print(f"registry: {sc.get('registry_run_id')}")
    print("=" * 72)
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="provenance", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("emit", help="Emit sidecar(s) + central manifest + registry for a run.")
    pe.add_argument("--output-dir", action="append", default=[], required=True,
                    help="Directory to write a RUN_<run_id>.prov.json into (repeatable).")
    pe.add_argument("--output-root", action="append", default=[],
                    help="File/dir to hash into the central manifest (repeatable; "
                         "defaults to --output-dir).")
    pe.add_argument("--command", default=None, help="The command line that produced this run.")
    pe.add_argument("--argv", default="", help="Space-separated argv of the producing command.")
    pe.add_argument("--label", default=None, help="Short human label for this run (e.g. 'stageA-default').")
    pe.add_argument("--manifest", default=None, help="Explicit central-manifest path.")
    pe.add_argument("--manifest-ref", default=None,
                    help="Point the sidecar at an EXISTING manifest (e.g. reproduce.sh's) "
                         "instead of writing a new one; implies --no-central.")
    pe.add_argument("--no-register", action="store_true", help="Skip the SQLite registry write.")
    pe.add_argument("--no-central", action="store_true", help="Skip the heavy central manifest.")
    pe.set_defaults(func=_cmd_emit)

    pr = sub.add_parser("reconstruct",
                        help="Emit a clearly-marked after-the-fact record for a PAST run "
                             "(facts must come from an authoritative log).")
    pr.add_argument("--output-dir", action="append", default=[], required=True,
                    help="Directory to write the reconstructed sidecar into (repeatable).")
    pr.add_argument("--output-root", action="append", default=[],
                    help="File/dir to hash into the central manifest (repeatable).")
    pr.add_argument("--run-id", default=None, help="Explicit run_id (use the run's real date).")
    pr.add_argument("--command", default=None, help="The command that produced the run.")
    pr.add_argument("--label", default=None, help="Short human label.")
    pr.add_argument("--created-utc", default=None, help="The run's real ISO-8601 UTC timestamp.")
    pr.add_argument("--git-commit", default=None, help="The commit the run actually executed on.")
    pr.add_argument("--branch", default=None, help="The branch the run executed on.")
    pr.add_argument("--wrapper-env", action="append", default=[],
                    help="KEY=VALUE env var that was in force (repeatable).")
    pr.add_argument("--reconstructed-from", default=None,
                    help="Authoritative source of the facts (e.g. the run log path).")
    pr.add_argument("--note", default=None, help="Free-text reconstruction note / caveats.")
    pr.add_argument("--manifest", default=None, help="Explicit central-manifest path.")
    pr.add_argument("--no-central", action="store_true", help="Skip the central manifest.")
    pr.add_argument("--no-resolve-world", action="store_true",
                    help="Do NOT apply the resolved world's catalog defaults "
                         "(record only the explicitly-supplied --wrapper-env).")
    pr.set_defaults(func=_cmd_reconstruct)

    ps = sub.add_parser("show", help="Show provenance for a result file or directory.")
    ps.add_argument("target", help="A result file or directory to look up.")
    ps.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
