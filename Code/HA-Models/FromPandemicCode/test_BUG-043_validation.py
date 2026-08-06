"""BUG-043 validation: confirm bug_fix encoding gives Case 1 agents 4 quarters.

Compares:
  Legacy mode (current code): Case 1 → 3 quarters of benefits (= the bug)
  bug_fix mode: Case 1 → 4 quarters of benefits (= the fix)

Uses deterministic trace through the actual loaded MrkvArray (which now
varies based on HAFISCAL_UI_STATE_ENCODING).
"""
import sys, os, io, contextlib
import numpy as np

def run_trace(encoding_mode):
    """Load MrkvArray under given encoding, trace Case 1 agent."""
    # Force a fresh import with the desired env var
    for mod in ['EstimParameters', 'Parameters']:
        if mod in sys.modules:
            del sys.modules[mod]
    os.environ['HAFISCAL_UI_STATE_ENCODING'] = encoding_mode

    sys.path.insert(0, '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode')
    sys.argv = ['test']
    with contextlib.redirect_stdout(io.StringIO()):
        import Parameters
        init_list = Parameters.return_parameters(Parametrization='Baseline')

    init_h = init_list[1]  # HS education group
    MrkvArray_recession = init_h['MrkvArray_recession'][0]
    MrkvArray_recessionUI = init_h['MrkvArray_recessionUI'][0]

    # Get the actual num_base_MrkvStates by reading from the imported module
    from EstimParameters import num_base_MrkvStates as J_micro
    n_macro = MrkvArray_recession.shape[0] // J_micro

    # Case 1 starting state: macro=3 (recession onset), micro=0 (employed)
    initial_state = 3 * J_micro + 0

    # Trace by always taking the highest-prob "stays unemployed" path
    # (= continued-unemployment trajectory)
    def trace(MrkvArray, T):
        state = initial_state
        history = [state]
        for t in range(T):
            probs = MrkvArray[state, :].copy()
            # Zero out transitions to employed (micro=0)
            for k in range(len(probs)):
                if k % J_micro == 0:
                    probs[k] = 0
            if probs.sum() == 0:
                break
            state = int(np.argmax(probs))
            history.append(state)
        return history

    rec_hist = trace(MrkvArray_recession, 12)
    recUI_hist = trace(MrkvArray_recessionUI, 12)

    # Count benefits-eligible periods (micro in {1, 2, ..., J_micro-2})
    # = all unemployed states except noBen (= micro = J_micro-1)
    # Note: in bug_fix, J_micro = 6 → benefit states are {1, 2, 3, 4} = u1Q-u4Q
    #       in legacy, J_micro = 4 → benefit states are {1, 2} = u1Q, u2Q
    # BUT under recession (no extension), only u1Q, u2Q give benefits regardless of encoding.
    # Under recessionUI, u3Q/u4Q give benefits too IF macro state is recession.
    # For simplicity, count states where the AGENT'S INCOME would be IncUnemp (0.7).
    # In legacy: u1Q, u2Q → 0.7 always
    # In bug_fix recession: u1Q, u2Q → 0.7; u3Q, u4Q → 0.5 (= no benefits)
    # In bug_fix recessionUI: u1Q, u2Q → 0.7; u3Q, u4Q → 0.7 if macro is recession

    # For benefits counting, look at the actual income at each (macro, micro)
    # by replicating the IncShkDstn rule
    def income_under_recession(macro, micro):
        if micro == 0: return 'wage'
        if micro in (1, 2): return 0.7  # u1Q, u2Q always benefits
        # micro >= 3: u3Q, u4Q (bug_fix only) or noBen (legacy 3)
        return 0.5  # no extension under recession

    def income_under_recessionUI(macro, micro, encoding):
        if micro == 0: return 'wage'
        if micro in (1, 2): return 0.7  # u1Q, u2Q always benefits
        if encoding == 'legacy':
            return 0.5  # micro 3 = noBen in 4-state legacy
        # bug_fix: micro = 3 (u3Q) or 4 (u4Q) → 0.7 if recession, else 0.5
        # micro 5 = noBen → always 0.5
        if micro in (3, 4):
            # Extension active iff macro is in recession (= odd index)
            if macro % 2 == 1:
                return 0.7
            return 0.5
        return 0.5  # noBen

    rec_benefits = sum(1 for s in rec_hist
                       if isinstance(income_under_recession(s // J_micro, s % J_micro), float)
                       and income_under_recession(s // J_micro, s % J_micro) > 0.6)
    recUI_benefits = sum(1 for s in recUI_hist
                         if isinstance(income_under_recessionUI(s // J_micro, s % J_micro, encoding_mode), float)
                         and income_under_recessionUI(s // J_micro, s % J_micro, encoding_mode) > 0.6)

    return {
        'encoding': encoding_mode,
        'J_micro': J_micro,
        'rec_history': [(s // J_micro, s % J_micro) for s in rec_hist],
        'recUI_history': [(s // J_micro, s % J_micro) for s in recUI_hist],
        'rec_benefits': rec_benefits,
        'recUI_benefits': recUI_benefits,
    }


print("=" * 78)
print("BUG-043 validation: Case 1 agent (employed at recession onset)")
print("=" * 78)

# Legacy mode
legacy = run_trace('legacy')
print(f"\nLegacy mode (J_micro={legacy['J_micro']}):")
print(f"  recession trajectory: {legacy['rec_history'][:8]}")
print(f"  recessionUI trajectory: {legacy['recUI_history'][:8]}")
print(f"  Benefits in recession: {legacy['rec_benefits']}")
print(f"  Benefits in recessionUI: {legacy['recUI_benefits']}")

# bug_fix mode
bugfix = run_trace('bug_fix')
print(f"\nbug_fix mode (J_micro={bugfix['J_micro']}):")
print(f"  recession trajectory: {bugfix['rec_history'][:8]}")
print(f"  recessionUI trajectory: {bugfix['recUI_history'][:8]}")
print(f"  Benefits in recession: {bugfix['rec_benefits']}")
print(f"  Benefits in recessionUI: {bugfix['recUI_benefits']}")

# Bug-fix verification
print()
print("=" * 78)
print("BUG-043 VERIFICATION")
print("=" * 78)
print(f"Case 1 benefits in recessionUI:")
print(f"  Legacy (= published code, has bug): {legacy['recUI_benefits']} quarters")
print(f"  bug_fix (= proposed fix):           {bugfix['recUI_benefits']} quarters")
print()
if legacy['recUI_benefits'] == 3 and bugfix['recUI_benefits'] == 4:
    print("✓✓✓ BUG-043 FIXED: bug_fix delivers 4 quarters; legacy delivered 3 ✓✓✓")
elif bugfix['recUI_benefits'] >= 4:
    print(f"~~ Partial: bug_fix delivers ≥4 ({bugfix['recUI_benefits']}); good")
else:
    print(f"✗ Bug NOT fixed by bug_fix mode: only {bugfix['recUI_benefits']} quarters")
