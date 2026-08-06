"""Concurrency + crash-safety tests for the solution_cache atomic write path.

Covers the write-race fix (deferred-followups item "solution_cache write-race
under concurrent run_welfare6_parallel"; plan R8 item 7): 12 welfare6 children
used to race ONE cache key's shared `.pkl.tmp`, so the first os.replace
consumed the tmp and every later writer died with FileNotFoundError on the
rename (pre-2ca4bfbc cache.py). The fixed write path gives each writer a
private tmp (`.tmp.<pid>.<uuid>`), publishes it with one atomic os.replace
(last-writer-wins — correct because same-key writers serialize the same
solution content by construction; see the INVARIANT comment in cache.py), and
sweeps tmps orphaned by killed writers.

WHY the READ path tolerates a concurrent replace (exercised by
test_reader_tolerates_concurrent_replace): a writer's bytes are complete,
flushed, and fsync'd to its private tmp BEFORE the single os.replace, and
os.replace is rename(2) on POSIX — it atomically swaps the directory entry
even when the destination exists. So at every instant the published path
either does not exist yet or names some writer's complete valid pickle. A
reader that open()ed the pre-replace file keeps its fd on the old inode
(POSIX keeps a replaced inode alive until the last fd closes) and reads
complete old bytes; a reader arriving after the replace opens the complete
new file. The cache never unlinks a published entry, so the exists()->open()
sequence in cached_eco_solve cannot hit FileNotFoundError either. No reader
ever opens a tmp name (inspect_cache/probe glob "*.pkl", which the tmp names
do not match), so partial bytes are never observable.

Forced-slow writes: cache's serializer is monkeypatched per-process (a
pickle-module shim whose dump() writes half the bytes, optionally signals,
sleeps, then writes the rest) so the tmp file is held open AND partially
written for a controlled window — maximizing collision overlap and giving the
crash test a guaranteed mid-write instant to SIGKILL.

Conventions follow test_sha_excluded_from_key.py: plain pytest test functions,
also runnable directly via `python test_write_race.py`. Fork-based
multiprocessing (POSIX-only; skipped elsewhere).
"""
import json
import multiprocessing
import os
import pickle
import shutil
import sys
import tempfile
import time
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import cache  # noqa: E402
from cache import (  # noqa: E402
    _TMP_NAME_RE, _cleanup_orphan_tmps, _unique_tmp, save_to_cache,
)

try:
    _CTX = multiprocessing.get_context("fork")  # children inherit the patches
except ValueError:  # non-POSIX
    _CTX = None

pytestmark = pytest.mark.skipif(_CTX is None, reason="requires POSIX fork")

KEY = "f" * 64  # well-formed fake SHA256 key
INPUTS = {"test": "write_race", "shock_type": "recession"}  # json-serializable

# Originals, for restoring parent-process patches.
_REAL_PICKLE = cache.pickle
_REAL_EXTRACT = cache.extract_eco_solution


def _paths(dir_path):
    """Production-shaped names: <human-tag>__<short-hash>.{pkl,meta.json}."""
    return (os.path.join(dir_path, "racetag__%s.pkl" % KEY[:8]),
            os.path.join(dir_path, "racetag__%s.meta.json" % KEY[:8]))


def _patch_serializer(extracted, mid_write_sleep=0.0, mid_write_event=None):
    """Monkeypatch cache (in THIS process only) for eco-free, forced-slow saves:
    - cache.extract_eco_solution returns `extracted` (no real economy needed);
    - cache.pickle.dump writes half the bytes, flushes (partial bytes ON DISK
      in the writer's private tmp), signals mid_write_event if given, sleeps
      mid_write_sleep, then writes the rest.
    """
    def _slow_dump(obj, f, protocol=None):
        data = _REAL_PICKLE.dumps(obj, protocol=protocol)
        half = len(data) // 2
        f.write(data[:half])
        f.flush()
        if mid_write_event is not None:
            mid_write_event.set()
        if mid_write_sleep:
            time.sleep(mid_write_sleep)
        f.write(data[half:])

    shim = types.SimpleNamespace(
        dump=_slow_dump,
        dumps=_REAL_PICKLE.dumps,
        load=_REAL_PICKLE.load,
        loads=_REAL_PICKLE.loads,
        HIGHEST_PROTOCOL=_REAL_PICKLE.HIGHEST_PROTOCOL,
    )
    cache.extract_eco_solution = lambda eco: extracted
    cache.pickle = shim


def _restore_serializer():
    cache.pickle = _REAL_PICKLE
    cache.extract_eco_solution = _REAL_EXTRACT


def _load_payload(pkl_path):
    with open(pkl_path, "rb") as f:
        return pickle.load(f)


def _tmp_names(dir_path):
    return sorted(n for n in os.listdir(dir_path) if _TMP_NAME_RE.search(n))


def _noop():
    pass


# ---------------------------------------------------------------- children --

def _hammer_writer(dir_path, barrier, result_q, writer_idx, mid_write_sleep):
    """One concurrent same-key writer (forked child)."""
    try:
        _patch_serializer({"marker": "race", "writer_idx": writer_idx,
                           "writer_pid": os.getpid()},
                          mid_write_sleep=mid_write_sleep)
        pkl_path, meta_path = _paths(dir_path)
        barrier.wait(timeout=30)
        save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)
        result_q.put(("ok", writer_idx))
    except Exception as e:  # noqa: BLE001 — report, parent asserts
        result_q.put(("err", writer_idx, repr(e)))


def _replace_writer(dir_path, result_q, n_saves, mid_write_sleep):
    """Repeatedly republish the same key (forked child)."""
    try:
        pkl_path, meta_path = _paths(dir_path)
        for i in range(n_saves):
            _patch_serializer({"marker": "race", "save_i": i,
                               "writer_pid": os.getpid()},
                              mid_write_sleep=mid_write_sleep)
            save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)
        result_q.put(("ok", n_saves))
    except Exception as e:  # noqa: BLE001
        result_q.put(("err", repr(e)))


def _reader_child(dir_path, done_evt, result_q):
    """Hammer open()+pickle.load on the published path while writers replace
    it. Every read must yield a complete valid payload (see module docstring
    for why os.replace atomicity guarantees this); any exception is a FAIL."""
    pkl_path, _ = _paths(dir_path)
    n_reads = 0
    try:
        while True:
            payload = _load_payload(pkl_path)
            assert payload["version"] == 1, payload
            assert payload["key"] == KEY, payload
            assert payload["extracted"]["marker"] == "race", payload
            n_reads += 1
            if done_evt.is_set():
                break
        result_q.put(("ok", n_reads))
    except Exception as e:  # noqa: BLE001
        result_q.put(("err", repr(e), n_reads))


def _doomed_writer(dir_path, mid_evt):
    """Writer to be SIGKILLed at a guaranteed mid-write instant (half the
    pickle bytes flushed to its private tmp)."""
    _patch_serializer({"marker": "race", "gen": "DOOMED",
                       "writer_pid": os.getpid()},
                      mid_write_sleep=120.0, mid_write_event=mid_evt)
    pkl_path, meta_path = _paths(dir_path)
    save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)  # never completes


# ------------------------------------------------------------------- tests --

def test_concurrent_writers_one_key():
    """8 forked writers hammer ONE key simultaneously with forced-slow writes
    (0.5 s mid-write sleep; a Barrier aligns them inside the window). Under the
    pre-fix shared-tmp scheme this reliably killed every writer after the first
    with FileNotFoundError on os.replace. Post-fix: all writers succeed, the
    surviving entry is exactly one writer's complete payload (last-writer-wins,
    no interleaving/corruption), the meta.json is valid, and no tmp files
    remain."""
    n = 8
    dir_path = tempfile.mkdtemp(prefix="hafiscal_write_race_")
    try:
        barrier = _CTX.Barrier(n)
        result_q = _CTX.Queue()
        procs = [_CTX.Process(target=_hammer_writer,
                              args=(dir_path, barrier, result_q, i, 0.5))
                 for i in range(n)]
        for p in procs:
            p.start()
        results = [result_q.get(timeout=60) for _ in range(n)]
        for p in procs:
            p.join(timeout=30)
        errs = [r for r in results if r[0] != "ok"]
        assert not errs, "writers failed under concurrency: %s" % (errs,)
        assert all(p.exitcode == 0 for p in procs), \
            [p.exitcode for p in procs]

        pkl_path, meta_path = _paths(dir_path)
        payload = _load_payload(pkl_path)
        assert payload["version"] == 1
        assert payload["key"] == KEY
        ex = payload["extracted"]
        assert ex["marker"] == "race" and ex["writer_idx"] in set(range(n)), ex
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta["key"] == KEY
        assert meta["pkl_filename"] == os.path.basename(pkl_path)
        strays = _tmp_names(dir_path)
        assert strays == [], "stray tmp files left behind: %s" % strays
        print("OK  %d concurrent writers, one key: winner=writer %d, "
              "entry valid, no strays" % (n, ex["writer_idx"]))
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)


def test_reader_tolerates_concurrent_replace():
    """Readers loop open()+pickle.load on the published path while 3 writers
    republish it 6x each (forced-slow, partial-bytes-on-disk windows included).
    os.replace atomicity (rename(2) swaps the directory entry; complete bytes
    are fsync'd to the private tmp first; an already-open old inode survives
    until its fd closes) means every single read must return a complete valid
    payload — no EOFError/UnpicklingError ever."""
    dir_path = tempfile.mkdtemp(prefix="hafiscal_write_race_rd_")
    try:
        pkl_path, meta_path = _paths(dir_path)
        # Pre-populate so readers always have an entry to open.
        _patch_serializer({"marker": "race", "save_i": -1,
                           "writer_pid": os.getpid()})
        try:
            save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)
        finally:
            _restore_serializer()

        done_evt = _CTX.Event()
        wq, rq = _CTX.Queue(), _CTX.Queue()
        writers = [_CTX.Process(target=_replace_writer,
                                args=(dir_path, wq, 6, 0.02))
                   for _ in range(3)]
        readers = [_CTX.Process(target=_reader_child,
                                args=(dir_path, done_evt, rq))
                   for _ in range(2)]
        for p in writers + readers:
            p.start()
        w_results = [wq.get(timeout=60) for _ in range(len(writers))]
        done_evt.set()
        r_results = [rq.get(timeout=60) for _ in range(len(readers))]
        for p in writers + readers:
            p.join(timeout=30)

        assert all(r[0] == "ok" for r in w_results), w_results
        bad = [r for r in r_results if r[0] != "ok"]
        assert not bad, "reader hit invalid/partial entry: %s" % (bad,)
        n_reads = sum(r[1] for r in r_results)
        assert n_reads >= 10, "too few reads to exercise concurrency: %d" % n_reads
        payload = _load_payload(pkl_path)  # final entry valid too
        assert payload["version"] == 1 and payload["key"] == KEY
        assert _tmp_names(dir_path) == []
        print("OK  %d reads during 18 concurrent replaces, all valid" % n_reads)
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)


def test_crash_mid_write_leaves_no_corrupt_entry():
    """SIGKILL a writer at a guaranteed mid-write instant (half the pickle
    bytes flushed to its private tmp). The partial bytes exist ONLY under the
    tmp name, which no reader opens — so the previously published entry must
    remain fully readable. The orphaned tmp must then be swept by (a) a direct
    _cleanup_orphan_tmps call (dead-pid rule, no age wait) and (b) the sweep
    built into the next successful save."""
    dir_path = tempfile.mkdtemp(prefix="hafiscal_write_race_kill_")
    try:
        pkl_path, meta_path = _paths(dir_path)
        # Pre-populate generation A.
        _patch_serializer({"marker": "race", "gen": "A"})
        try:
            save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)
        finally:
            _restore_serializer()

        mid_evt = _CTX.Event()
        p = _CTX.Process(target=_doomed_writer, args=(dir_path, mid_evt))
        p.start()
        assert mid_evt.wait(timeout=30), "writer never reached mid-write"
        tmps = _tmp_names(dir_path)
        assert len(tmps) == 1 and (".tmp.%d." % p.pid) in tmps[0], tmps
        p.kill()   # SIGKILL: no finally-cleanup runs in the child
        p.join(timeout=30)  # reap, so the pid probes dead (not a zombie)
        assert not p.is_alive()

        # (i) The published entry is untouched and valid (readers see gen A).
        payload = _load_payload(pkl_path)
        assert payload["version"] == 1 and payload["key"] == KEY
        assert payload["extracted"]["gen"] == "A", payload["extracted"]
        # (ii) The orphan is present, then swept by the dead-pid rule.
        assert _tmp_names(dir_path) == tmps
        _cleanup_orphan_tmps(dir_path)
        assert _tmp_names(dir_path) == [], "orphan not swept"
        # (iii) Production hook: plant another dead-pid orphan; a normal save
        # must sweep it and publish generation B.
        orphan = os.path.join(
            dir_path, "%s.tmp.%d.%s" % (os.path.basename(pkl_path), p.pid,
                                        "0" * 32))
        with open(orphan, "wb") as f:
            f.write(b"partial garbage from a crashed writer")
        _patch_serializer({"marker": "race", "gen": "B"})
        try:
            save_to_cache(None, KEY, INPUTS, pkl_path, meta_path)
        finally:
            _restore_serializer()
        assert not os.path.exists(orphan), "save did not sweep the orphan"
        assert _load_payload(pkl_path)["extracted"]["gen"] == "B"
        assert _tmp_names(dir_path) == []
        print("OK  SIGKILL mid-write: old entry intact, orphan swept "
              "(direct + via next save)")
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)


def test_tmp_naming_and_cleanup_rules():
    """Pin the tmp-name contract and the sweep's conservative rules: unique
    per call; pid parseable by _TMP_NAME_RE; live-pid recent tmps and recent
    legacy '.tmp' files are KEPT; age fallback and dead-pid rule remove;
    published files are never touched."""
    a, b = _unique_tmp("/x/y.pkl"), _unique_tmp("/x/y.pkl")
    assert a != b, "tmp names must be unique per call"
    m = _TMP_NAME_RE.search(os.path.basename(a))
    assert m and int(m.group(1)) == os.getpid()
    m_legacy = _TMP_NAME_RE.search("y.pkl.tmp")
    assert m_legacy and m_legacy.group(1) is None
    assert _TMP_NAME_RE.search("y.pkl") is None
    assert _TMP_NAME_RE.search("y.meta.json") is None

    dir_path = tempfile.mkdtemp(prefix="hafiscal_write_race_rules_")
    try:
        old = time.time() - 7 * 3600  # older than the 6 h age fallback
        def _mk(name, mtime=None):
            fp = os.path.join(dir_path, name)
            with open(fp, "wb") as f:
                f.write(b"x")
            if mtime is not None:
                os.utime(fp, (mtime, mtime))
            return fp

        # A genuinely dead pid: fork a no-op child and reap it.
        d = _CTX.Process(target=_noop)
        d.start()
        d.join(timeout=30)
        dead_pid = d.pid

        keep_live = _mk("k.pkl.tmp.%d.%s" % (os.getpid(), "a" * 32))
        drop_aged = _mk("k2.pkl.tmp.%d.%s" % (os.getpid(), "b" * 32), old)
        keep_legacy = _mk("k3.pkl.tmp")
        drop_legacy = _mk("k4.pkl.tmp", old)
        drop_dead = _mk("k5.pkl.tmp.%d.%s" % (dead_pid, "c" * 32))
        keep_pub = _mk("k6.pkl", old)  # published: never a sweep candidate

        _cleanup_orphan_tmps(dir_path)
        left = sorted(os.listdir(dir_path))
        assert os.path.basename(keep_live) in left, "live recent tmp removed"
        assert os.path.basename(keep_legacy) in left, "recent legacy removed"
        assert os.path.basename(keep_pub) in left, "published file removed"
        assert os.path.basename(drop_aged) not in left, "aged tmp kept"
        assert os.path.basename(drop_legacy) not in left, "aged legacy kept"
        assert os.path.basename(drop_dead) not in left, "dead-pid tmp kept"
        print("OK  naming contract + sweep rules (dead-pid, age, keep-live)")
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)


if __name__ == "__main__":
    test_concurrent_writers_one_key()
    test_reader_tolerates_concurrent_replace()
    test_crash_mid_write_leaves_no_corrupt_entry()
    test_tmp_naming_and_cleanup_rules()
    print("All write-race tests passed.")
