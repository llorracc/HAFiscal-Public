"""Guard tests for the unified run-provenance emitter (provenance.py).

Covers the load-bearing invariants of the design plan:
- the sidecar validates against provenance_sidecar.schema.json,
- emit() writes a sibling sidecar into each output dir and returns a run_id,
- provenance NEVER modifies a result file's bytes (the LOCKED_TABLES + two-machine
  byte-comparison constraint),
- the reverse-lookup (`show` / find_sidecars) finds the sidecar,
- config.effective_config() reflects HAFISCAL_WORLD.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

_HA_ROOT = Path(__file__).resolve().parent
if str(_HA_ROOT) not in sys.path:
    sys.path.insert(0, str(_HA_ROOT))

import provenance  # noqa: E402

_SCHEMA_PATH = _HA_ROOT / "provenance_sidecar.schema.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_schema_file_exists_and_parses():
    assert _SCHEMA_PATH.exists(), "provenance_sidecar.schema.json missing"
    schema = json.loads(_SCHEMA_PATH.read_text())
    assert schema.get("title", "").startswith("HAFiscal run-provenance")


def test_schema_is_valid_draft7():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(_SCHEMA_PATH.read_text())
    # Raises SchemaError if the schema itself is malformed.
    jsonschema.Draft7Validator.check_schema(schema)


def test_any_committed_sidecars_validate():
    """Every RUN_*.prov.json present anywhere in the repo must validate.

    Acts as a CI-style guard: a malformed sidecar (e.g. from a schema bump that
    wasn't migrated) fails here. Skips cleanly when none are present.
    """
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(_SCHEMA_PATH.read_text())
    repo_root = _HA_ROOT.parent.parent
    sidecars = list(repo_root.rglob(f"{provenance.SIDECAR_PREFIX}*{provenance.SIDECAR_SUFFIX}"))
    if not sidecars:
        pytest.skip("no RUN_*.prov.json sidecars present in the repo")
    for sc in sidecars:
        data = json.loads(sc.read_text())
        jsonschema.validate(instance=data, schema=schema)


def test_gather_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(_SCHEMA_PATH.read_text())
    sidecar = provenance.gather(command="pytest synthetic", argv=["pytest", "x"],
                                label="unit-test")
    jsonschema.validate(instance=sidecar, schema=schema)
    # Load-bearing fields are populated.
    assert sidecar["run_id"]
    assert sidecar["schema_version"] == provenance.SCHEMA_VERSION
    assert isinstance(sidecar["wrapper_env"], dict)
    assert "world" in sidecar["resolved_config"]


def test_flag_surface_captured(monkeypatch):
    """The sidecar records SET registry flags + the full-surface counts (the
    reproducibility contract), and omits unset flags."""
    monkeypatch.setenv("HAFISCAL_NUM_STARTS", "4")
    sidecar = provenance.gather(command="pytest", argv=["pytest"])
    set_flags = sidecar.get("set_flags")
    reg = sidecar.get("env_flags_registry")
    assert isinstance(set_flags, dict)
    # The registry has ~120+ flags; a parser regression (capturing nothing)
    # must fail loudly.
    assert reg["flag_count"] >= 100, f"only {reg['flag_count']} flags in registry"
    assert reg["flags_set"] == len(set_flags)
    assert reg["flags_set"] + reg["flags_unset"] == reg["flag_count"]
    assert reg["sha256"], "registry sha256 must be pinned so unset=default is resolvable"
    # set_flags contains only SET registry flags (no nulls), and the var we set.
    assert "HAFISCAL_NUM_STARTS" in set_flags
    for k, v in set_flags.items():
        assert k.startswith("HAFISCAL_")
        assert isinstance(v, str), f"{k} should be a set string value, not {v!r}"


def test_emit_writes_sidecar_without_touching_results(tmp_path):
    # A fake result file whose bytes must NOT change.
    out_dir = tmp_path / "Results"
    out_dir.mkdir()
    result = out_dir / "DiscFacEstim_fake_ESC_candidate.txt"
    result.write_text("{'EducationGroup': 0, 'beta': 0.7278}\n")
    before = _sha(result)

    info = provenance.emit(
        [str(out_dir)],
        command="pytest emit",
        label="unit-test",
        register=False,   # don't touch the real SQLite registry in a unit test
        central=False,    # skip heavy pip-freeze capture
        verbose=False,
    )

    assert info["run_id"], info
    assert info["sidecars"], info
    # The result bytes are untouched.
    assert _sha(result) == before, "provenance must never modify result bytes"

    sc_path = Path(info["sidecars"][0])
    assert sc_path.exists()
    assert sc_path.name.startswith(provenance.SIDECAR_PREFIX)
    assert sc_path.name.endswith(provenance.SIDECAR_SUFFIX)

    sidecar = json.loads(sc_path.read_text())
    assert sidecar["run_id"] == info["run_id"]

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(_SCHEMA_PATH.read_text())
    jsonschema.validate(instance=sidecar, schema=schema)


def test_no_symlinks_created(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    provenance.emit([str(out_dir)], register=False, central=False, verbose=False)
    for child in out_dir.iterdir():
        assert not child.is_symlink(), "provenance must not create symlinks next to results"


def test_reverse_lookup_finds_sidecar(tmp_path):
    out_dir = tmp_path / "Results"
    out_dir.mkdir()
    result = out_dir / "AllResults_fake_ESC_candidate.txt"
    result.write_text("body\n")
    provenance.emit([str(out_dir)], register=False, central=False, verbose=False)

    # Looking up the result file finds the sidecar in its parent dir.
    found = provenance.find_sidecars(str(result))
    assert found, "find_sidecars should locate the sibling sidecar"
    sc = provenance.load_sidecar(found[0])
    assert sc["run_id"]


def test_effective_config_reflects_world(monkeypatch):
    cfg = pytest.importorskip("config", reason="config package import")
    monkeypatch.setenv("HAFISCAL_WORLD", "as-corrected")
    ec = cfg.effective_config()
    assert ec["world"] == "as-corrected"
    assert ec["world_known"] is True

    monkeypatch.setenv("HAFISCAL_WORLD", "default")
    ec = cfg.effective_config()
    assert ec["world"] == "default"

    # An unknown world is reported, not raised.
    monkeypatch.setenv("HAFISCAL_WORLD", "nonsense-world")
    ec = cfg.effective_config()
    assert ec["world"] == "nonsense-world"
    assert ec["world_known"] is False


def test_central_manifest_writes_and_hashes_outputs(tmp_path):
    out_dir = tmp_path / "Results"
    out_dir.mkdir()
    result = out_dir / "fake_output.txt"
    result.write_text("hello\n")
    manifest_path = tmp_path / "manifest.json"

    sidecar = provenance.gather(command="pytest central", run_id="testrun_000000")
    written = provenance.write_central_manifest(manifest_path, sidecar, [str(out_dir)])
    assert written.exists()
    manifest = json.loads(written.read_text())
    assert manifest["schema_version"] == provenance.SCHEMA_VERSION
    assert manifest["run_id"] == "testrun_000000"
    # The fake output was hashed; the sidecar (if any) and tmp files excluded.
    out_keys = list(manifest["outputs"].keys())
    assert any("fake_output.txt" in k for k in out_keys)
    assert not any(k.endswith(provenance.SIDECAR_SUFFIX) for k in out_keys)
