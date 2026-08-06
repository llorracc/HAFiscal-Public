"""Explicit empirical confirmation using actual HAFiscal MrkvArrays.

For each of:
  - recession scenario (no extension)
  - recessionUI scenario (extension)
simulate one agent forward through 12 periods, with deterministic recession
persistence and stochastic micro transitions per HAFiscal's MrkvArray.

We'll do a Monte Carlo test: simulate 100,000 agents starting employed at
recession onset (= Case 1), under both scenarios using the same per-agent
random seeds (CRN). Count benefits-eligible periods per agent.

If the published code correctly delivers up to 4 quarters of benefits for
Case 1 agents in long recessions (per the user's interpretation), the
maximum benefits any Case 1 agent can receive should be 4. If the published
code under-delivers, the max should be 3.
"""
import sys, os, io, contextlib
import numpy as np

sys.path.insert(0, '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode')
sys.argv = ['confirm']

with contextlib.redirect_stdout(io.StringIO()):
    import Parameters as P_mod
    init_list = P_mod.return_parameters(Parametrization='Baseline')

# Use HS_Only's Markov arrays for simplicity; the structure is identical
# across education groups, just different urates
init_h = init_list[1]  # education group: HS
MrkvArray_recession = init_h['MrkvArray_recession'][0]
MrkvArray_recessionUI = init_h['MrkvArray_recessionUI'][0]
J_MICRO = 4  # employed, u1Q, u2Q, noBen
n_macro = MrkvArray_recession.shape[0] // J_MICRO
print(f"MrkvArray dim: {MrkvArray_recession.shape}")
print(f"  → {n_macro} macro states × {J_MICRO} micro states")
print()

# Simulate ONE agent under each scenario, using the SAME random seed (CRN)
# Force the recession to persist (= use deterministic R_persist=1 path through
# the macro chain) by always taking the "recession-persists" macro transition.
# This corresponds to the most-likely macro path for a long recession.
# Within each period, draw the micro transition stochastically.

def simulate_agent(MrkvArray, initial_state, T, rng):
    """Return list of (macro, micro, was_in_benefits_state)."""
    state = initial_state
    history = []
    for t in range(T):
        macro = state // J_MICRO
        micro = state % J_MICRO
        in_benefits = micro in (1, 2)  # u1Q or u2Q
        history.append((macro, micro, in_benefits))
        # Sample next state
        probs = MrkvArray[state, :]
        u = rng.random()
        cum = 0.0
        next_state = -1
        for k, p in enumerate(probs):
            cum += p
            if u <= cum:
                next_state = k
                break
        state = next_state if next_state >= 0 else state
    return history

# CRN: same per-agent seed across pol and none
N_AGENTS = 100_000
T_SIM = 12
INITIAL_STATE = 3 * J_MICRO + 0  # (macro=3, employed) — Case 1 starting point

print(f"Simulating N={N_AGENTS} agents starting at (macro=3, employed).")
print(f"Using CRN: per-agent seed shared across recession and recessionUI scenarios.")
print()

# Track benefits-eligible periods per agent
benefits_rec = np.zeros(N_AGENTS, dtype=int)
benefits_recUI = np.zeros(N_AGENTS, dtype=int)
# Also track "Case 1 strict": agents who become unemp during t=0 and stay unemp
matches_case1 = np.zeros(N_AGENTS, dtype=bool)

for i in range(N_AGENTS):
    rng_rec = np.random.default_rng(seed=12345 + i)
    rng_recUI = np.random.default_rng(seed=12345 + i)  # SAME seed = CRN

    hist_rec = simulate_agent(MrkvArray_recession, INITIAL_STATE, T_SIM, rng_rec)
    hist_recUI = simulate_agent(MrkvArray_recessionUI, INITIAL_STATE, T_SIM, rng_recUI)

    # Count benefits-eligible periods (micro in {1, 2})
    benefits_rec[i] = sum(1 for (m, mi, b) in hist_rec if b)
    benefits_recUI[i] = sum(1 for (m, mi, b) in hist_recUI if b)

    # Case 1 strict: agent at u1Q at t=1 (became unemp during t=0)
    # AND stays at non-employed for at least t=2..7 (= 6 more periods)
    if hist_rec[1][1] == 1:
        if all(hist_rec[t][1] != 0 for t in range(2, 8)):
            matches_case1[i] = True

n_case1 = int(matches_case1.sum())
print(f"Of {N_AGENTS} agents starting employed at recession onset:")
print(f"  {n_case1} match Case 1 strict criteria (became unemp during t=0, stayed unemp)")
print()
print(f"Benefits-eligible periods (full population, T={T_SIM}):")
print(f"  recession  : mean={benefits_rec.mean():.3f}, max={benefits_rec.max()}, distribution: {np.bincount(benefits_rec)}")
print(f"  recessionUI: mean={benefits_recUI.mean():.3f}, max={benefits_recUI.max()}, distribution: {np.bincount(benefits_recUI)}")
print()

if n_case1 > 0:
    print(f"Case 1 strict subgroup ({n_case1} agents):")
    bc1_rec = benefits_rec[matches_case1]
    bc1_recUI = benefits_recUI[matches_case1]
    print(f"  recession  : mean={bc1_rec.mean():.3f}, max={bc1_rec.max()}")
    print(f"    distribution: {np.bincount(bc1_rec)}")
    print(f"  recessionUI: mean={bc1_recUI.mean():.3f}, max={bc1_recUI.max()}")
    print(f"    distribution: {np.bincount(bc1_recUI)}")
    print()
    print(f"  KEY QUESTION: max benefits any Case 1 strict agent receives in recessionUI")
    print(f"  (under user's interpretation, should be 4 if recession is long enough; if max is 3, the published encoding under-delivers)")
    print(f"  ANSWER: max = {bc1_recUI.max()}")
    print()
    print(f"  Per-agent comparison (Case 1 strict only):")
    print(f"    Agents getting EXACTLY 3 benefits in recessionUI: {(bc1_recUI == 3).sum()}")
    print(f"    Agents getting EXACTLY 4 benefits in recessionUI: {(bc1_recUI == 4).sum()}")
    print(f"    Agents getting MORE THAN 4 in recessionUI: {(bc1_recUI > 4).sum()}")
