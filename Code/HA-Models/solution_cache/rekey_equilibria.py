#!/usr/bin/env python3
"""Re-key AD-equilibrium store entries whose `solver_source` leaf was computed from a stale source read (2026-08-28:
`inspect.getsource` at first SAVE after a mid-run edit of AggFiscalModel.py; see the pin at the end of that module).
The equilibrium is a property of the model, not of the hash; the entry is copied under the key every clean import
produces, with `rekeyed_from` provenance. The stale entries are left in place (they match nothing).

usage: python rekey_equilibria.py --from-hash <prefix> [--to-hash <full hash>] [--apply]
       python rekey_equilibria.py --any-with-leaf --drop-env-leaf HAFISCAL_TM_A_INDEXED [--move] [--apply]
       python rekey_equilibria.py --missing-leaf --add-env-leaf HAFISCAL_ONSET_SPIKE_T0_EXEMPT=0 [--move] [--apply]
         (BUG-122 Step 0, 2026-09-06: a NEW key leaf makes every existing entry unreachable. Each was
          produced without the onset-spike exemption, so each belongs at that leaf's OFF value; this
          re-keys them there rather than making the welfare battery re-derive equilibria it already has.)
         (BUG-119 option 2, 2026-09-02: every CURRENT-hash entry still keyed on an engine-selection leaf is
          re-keyed without it, the leaf's value backfilled into conventions.producer_env; --move deletes the
          old-keyed pkl+meta once the new pair is written -- the old key matches nothing after option 2)
  --to-hash defaults to the CURRENT solver_source_hash() of this checkout; without --apply only reports.
"""
import argparse, glob, hashlib, json, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FromPandemicCode"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--from-hash", default=None, help="solver_source prefix to re-key")
    ap.add_argument("--stale-since", default=None, help="HH:MM today: re-key every entry saved after this time whose solver_source differs from --to-hash")
    ap.add_argument("--to-hash", default=None)
    ap.add_argument("--drop-env-leaf", action="append", default=[], help="remove this env leaf from the stored inputs before re-keying (an entry published while a consumer-only flag sat in the key whitelist, BUG-098)")
    ap.add_argument("--any-with-leaf", action="store_true", help="select every CURRENT-hash entry whose stored inputs.env carries a --drop-env-leaf (BUG-119 option 2)")
    ap.add_argument("--add-env-leaf", action="append", default=[], metavar="NAME=VALUE", help="add this env leaf to the stored inputs before re-keying (a leaf that entered the key whitelist AFTER the entry was written, BUG-122 Step 0)")
    ap.add_argument("--missing-leaf", action="store_true", help="select every CURRENT-hash entry whose stored inputs.env LACKS an --add-env-leaf name")
    ap.add_argument("--move", action="store_true", help="delete the old-keyed pkl+meta after the new pair is written (the old key matches nothing)")
    ap.add_argument("--apply", action="store_true"); a = ap.parse_args()
    sys.argv = sys.argv[:1]
    from solution_cache import policy_store as _ps
    to_hash = a.to_hash or _ps.solver_source_hash()
    eq_dir = os.path.join(_ps.store_dir(), "equilibrium")
    n = 0
    for meta_path in sorted(glob.glob(os.path.join(eq_dir, "??", "*.meta.json"))):
        meta = json.load(open(meta_path)); inputs = meta.get("inputs") or {}
        src = str(inputs.get("solver_source", ""))
        if a.from_hash and not src.startswith(a.from_hash):
            continue
        if a.stale_since:
            hh, mm = map(int, a.stale_since.split(":")); lt = time.localtime()
            since = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
            leaves_present = any(k in (inputs.get("env") or {}) for k in a.drop_env_leaf)
            if meta.get("saved_at", 0) < since or (src == to_hash and not leaves_present):
                continue
        if a.any_with_leaf:
            if not a.drop_env_leaf:
                sys.exit("--any-with-leaf needs at least one --drop-env-leaf")
            if src != to_hash or not any(k in (inputs.get("env") or {}) for k in a.drop_env_leaf):
                continue
        elif a.missing_leaf:
            if not a.add_env_leaf:
                sys.exit("--missing-leaf needs at least one --add-env-leaf NAME=VALUE")
            names = [kv.split("=", 1)[0] for kv in a.add_env_leaf]
            if src != to_hash or all(k in (inputs.get("env") or {}) for k in names):
                continue
        elif not a.from_hash and not a.stale_since:
            sys.exit("give --from-hash, --stale-since, --any-with-leaf or --missing-leaf")
        new_inputs = dict(inputs); new_inputs["solver_source"] = to_hash
        if a.drop_env_leaf:
            env = dict(new_inputs.get("env") or {})
            dropped = [k for k in a.drop_env_leaf if k in env]
            for k in dropped: env.pop(k)
            new_inputs["env"] = env
        if a.add_env_leaf:
            env = dict(new_inputs.get("env") or {})
            for kv in a.add_env_leaf:
                k, _, v = kv.partition("=")
                env.setdefault(k, v)
            new_inputs["env"] = env
        canonical = json.dumps(new_inputs, sort_keys=True, separators=(",", ":"), default=str)
        new_key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        d = os.path.join(eq_dir, new_key[:2]); new_pkl = os.path.join(d, f"{new_key}.pkl"); new_meta = os.path.join(d, f"{new_key}.meta.json")
        print(f"{str(meta.get('shock_type')):16s} {str(meta.get('key'))[:16]} -> {new_key[:16]}  saved {time.strftime('%m-%d %H:%M', time.localtime(meta.get('saved_at', 0)))}"
              f"  producer={meta.get('producer', {}).get('site')}  {'EXISTS' if os.path.exists(new_pkl) else ''}")
        n += 1
        if not a.apply or os.path.exists(new_pkl):
            continue
        os.makedirs(d, exist_ok=True)
        payload = pickle.load(open(meta_path[:-len(".meta.json")] + ".pkl", "rb")); payload["key"] = new_key
        _ps._atomic_pickle_write(new_pkl, payload)
        new_m = dict(meta); new_m["key"] = new_key; new_m["inputs"] = new_inputs
        new_m["rekeyed_from"] = {"key": meta["key"], "solver_source": inputs.get("solver_source"), "at": time.time(),
                                 "dropped_env_leaves": [k for k in a.drop_env_leaf if k in (inputs.get("env") or {})],
                                 "added_env_leaves": list(a.add_env_leaf),
                                 "reason": ((("BUG-119 option 2: engine-selection env leaves removed from the key" if a.any_with_leaf
                                             else "BUG-098: consumer-only env leaves removed from the key")) if a.drop_env_leaf else
                                            ("BUG-122 Step 0: a key leaf added after the entry was written" if a.add_env_leaf else
                                             "stale inspect.getsource at first SAVE after a mid-run edit (2026-08-28); hashed function bodies unchanged"))}
        if a.drop_env_leaf:   # the dropped leaves travel into the conventions (the producer's record)
            conv = dict(new_m.get("conventions") or {}); penv = dict(conv.get("producer_env") or {})
            old_env = inputs.get("env") or {}
            for k in a.drop_env_leaf:
                if k in old_env: penv[k] = old_env.get(k, "")
            conv["producer_env"] = penv; new_m["conventions"] = conv
        _ps._atomic_json_write(new_meta, new_m); print("   written")
        if a.move:
            os.remove(meta_path[:-len(".meta.json")] + ".pkl"); os.remove(meta_path); print("   old entry removed (--move)")
    sel = a.from_hash or (("stale since " + a.stale_since) if a.stale_since else
                          ("missing-leaf " + ",".join(a.add_env_leaf) if a.missing_leaf
                           else "any-with-leaf " + ",".join(a.drop_env_leaf)))
    print(f"{n} entries matched {sel}")


if __name__ == "__main__":
    main()
