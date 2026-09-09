"""Guards for the BUG-071 bug class (stale labeled-distribution views).

HARK labeled distributions (DiscreteDistributionLabeled and subclasses,
e.g. BufferStockIncShkDstn) carry positional arrays (.atoms/.pmv) plus
labeled views (.dataset xarray + cached ._wrapped_atoms) that alias the
same memory ONLY at fresh construction. Two idioms sever the aliasing:
  1. copy.deepcopy of the distribution (directly, or of any agent or
     economy containing one);
  2. whole-attribute rebind, d.atoms = (...).
After severing, positional mutations never reach the labeled views, and
HARK's labels-aware consumers (expected() with shocks["Name"] access,
.dataset reads, dist_of_func) silently read stale pre-mutation values.
BUG-071: the Step-4 HANK/SAM solves consumed pre-scaling income for the
published-era pipeline this way.

The 2026-08-08 class sweep (plans/20260808-1539h, verdicts in
conclusions_private/) found the conjunction fires nowhere else: severed
labeled views are widespread, but every reachable consumer outside the
Step-4 solver is positional. assert_labeled_consistent() is the runtime
predicate; test_labeled_dstn_guard.py keeps the census true.
"""
import numpy as np

__all__ = ["assert_labeled_consistent", "is_labeled", "labeled_views_consistent"]


def is_labeled(d):
    """True if d is a labels-carrying HARK distribution."""
    return hasattr(d, "_wrapped_atoms") and hasattr(d, "dataset")


def labeled_views_consistent(d, rtol=0.0, atol=0.0):
    """VALUE-equality of positional atoms vs both labeled views.

    Value equality (not shared memory) is the correct predicate: a
    severed-but-unmutated copy is harmless, and the Step-4 SHOCK_FIX
    produces relabeled objects that later travel through deepcopy.
    """
    if not is_labeled(d):
        return True
    atoms = np.atleast_2d(np.asarray(d.atoms, dtype=float))
    for i, name in enumerate(d.dataset.data_vars):
        row = atoms[i].ravel()
        wrapped = np.asarray(d._wrapped_atoms[name], dtype=float).ravel()
        ds = np.asarray(d.dataset[name].values, dtype=float).ravel()
        if not (np.allclose(row, wrapped, rtol=rtol, atol=atol)
                and np.allclose(row, ds, rtol=rtol, atol=atol)):
            return False
    return True


def assert_labeled_consistent(d, name=""):
    """Raise AssertionError naming the object if labeled views are stale."""
    if not labeled_views_consistent(d):
        raise AssertionError(
            f"stale labeled distribution views{' in ' + name if name else ''}: "
            "positional .atoms disagree with .dataset/._wrapped_atoms — a "
            "labels-aware consumer (expected()/dataset) would read wrong "
            "values. Rebuild via DiscreteDistributionLabeled after mutating "
            "(see BUG-071)."
        )
