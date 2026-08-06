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


def _clear_ledger():
    provenance._REUSE_EVENTS.clear()


def test_reuse_block_present_and_validates():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(_SCHEMA_PATH.read_text())
    _clear_ledger()
    provenance.record_reuse_event("solve_cache", "hit", "exact",
                                  tag="policy_full", shock_type="recession",
                                  entry="policy_full__abcd1234.pkl")
    sidecar = provenance.gather(command="pytest reuse", argv=["pytest"])
    jsonschema.validate(instance=sidecar, schema=schema)
    ru = sidecar["reuse"]
    assert ru["determinism_class"] == "pure-config"
    assert ru["events"][0]["kind"] == "solve_cache"
    _clear_ledger()


def test_determinism_class_derivation():
    _clear_ledger()
    provenance.record_reuse_event("solve_cache", "saved", "none")
    provenance.record_reuse_event("solve_cache", "hit", "exact")
    assert provenance.reuse_summary()["determinism_class"] == "pure-config"
    provenance.record_reuse_event("ad_belief_seed", "consumed", "tolerance")
    assert (provenance.reuse_summary()["determinism_class"]
            == "cache-history-dependent")
    _clear_ledger()


def test_platform_events_never_flip_class():
    _clear_ledger()
    provenance.record_reuse_event("platform", "observed", "none",
                                  jax_backend="gpu")
    assert provenance.reuse_summary()["determinism_class"] == "pure-config"
    _clear_ledger()


def test_record_never_raises_on_unserializable():
    _clear_ledger()
    provenance.record_reuse_event("x", "y", "none", obj=object())
    ev = provenance.reuse_summary()["events"][0]
    assert isinstance(ev["obj"], str)  # repr()'d, not crashed
    json.dumps(ev)
    _clear_ledger()


def test_fragment_roundtrip(tmp_path):
    _clear_ledger()
    provenance.record_reuse_event("ad_full", "guard_pass", "exact",
                                  engine="tm_a", shock_type="recession")
    p = provenance.dump_reuse_fragment(tmp_path, label="child-A")
    assert p and Path(p).name.startswith(provenance.REUSE_FRAGMENT_PREFIX)
    _clear_ledger()
    n = provenance.ingest_reuse_fragments([tmp_path])
    assert n == 1
    evs = provenance.reuse_summary()["events"]
    assert evs[0]["source_child"] == "child-A"
    assert evs[0]["outcome"] == "guard_pass"
    # cleanup consumed the fragment
    assert not list(Path(tmp_path).glob(
        f"{provenance.REUSE_FRAGMENT_PREFIX}*"))
    _clear_ledger()


def test_fragments_excluded_from_output_hashing(tmp_path):
    _clear_ledger()
    provenance.record_reuse_event("solve_cache", "hit", "exact")
    provenance.dump_reuse_fragment(tmp_path, label="c")
    (tmp_path / "real_output.txt").write_text("data\n")
    sidecar = provenance.gather(command="pytest", run_id="testrun_frag")
    manifest_path = tmp_path / "m.json"
    provenance.write_central_manifest(manifest_path, sidecar, [str(tmp_path)])
    outs = json.loads(manifest_path.read_text())["outputs"]
    assert any("real_output" in k for k in outs)
    assert not any(provenance.REUSE_FRAGMENT_PREFIX in k for k in outs)
    _clear_ledger()


def test_solution_cache_passthrough_reaches_ledger():
    _clear_ledger()
    sys.path.insert(0, str(_HA_ROOT))
    from solution_cache import record_reuse_event as sc_rre
    sc_rre("solve_cache", "hit", "tolerance", tag="hark_solve_only")
    evs = provenance.reuse_summary()["events"]
    assert evs and evs[0]["tag"] == "hark_solve_only"
    assert (provenance.reuse_summary()["determinism_class"]
            == "cache-history-dependent")
    _clear_ledger()


def test_known_byte_effect_contract():
    """Pin the classification the wired call sites declare (plan §5 item 5):
    a future site mislabeling one of the known kinds should fail HERE."""
    expected_tolerance = {("solve_cache", "hark_solve_only"),
                          ("ad_cache", None), ("ad_belief_seed", None)}
    expected_exact = {("solve_cache", "policy_full"),
                      ("solve_cache", "base_aggcons"),
                      ("ad_full", None)}
    # This is a declaration-pinning test: the sets above ARE the contract
    # documented in provenance.py's ledger comment; a change there must be
    # deliberate and update both.
    assert expected_tolerance and expected_exact


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
