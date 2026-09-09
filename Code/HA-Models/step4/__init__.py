"""Step-4 (Section 5, HANK-SAM) live engine — importable stages.

L4 of the rebuild plan (plans/20260808-1638h S3.1 via 20260809-0006h):
the historical monolith pair
    FromPandemicCode/HA-Fiscal-HANK-SAM.py            (household Jacobians)
    FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py  (GE/SAM experiments)
is FROZEN as the QE-fidelity engine (it reproduces the published
construction bit-for-bit under HAFISCAL_QE_FIDELITY=1, historical bugs
included), and this package is the LIVE default path:

    hh_setup    calibration ingestion + SAM chain + income distributions
                (fixed semantics only: BUG-071/072/073 corrections are
                structural here, not flag arms)
    jacobians   fake-news household Jacobians -> HA_Fiscal_Jacs.obj
    ge          GE/SAM models + policy experiments -> multiplier pickle
    figures     the paper's Section-5 figure family (candidate-routed)

Entry points (what do_all.py Step 4 invokes): run_jacobians.py, run_ge.py.
Both route to the frozen monolith when the caller asks for historical
semantics (HAFISCAL_QE_FIDELITY=1, an explicit historical escape flag, or
HAFISCAL_STEP4_ENGINE=monolith) — the package itself implements only the
fixed construction.

Equivalence contract at birth (gates in the L4 night-log): package
default output ≡ monolith default output at the byte/1e-15 class on the
same machine, for both the Jacobian obj and the GE pickle.
"""
