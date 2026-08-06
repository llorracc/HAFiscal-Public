"""Trace the 9 Case 1 agents who got 4 benefits in recessionUI.
What macro/micro path did they take?
"""
import sys, os, io, contextlib
import numpy as np

sys.path.insert(0, '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode')
sys.argv = ['trace_outliers']
with contextlib.redirect_stdout(io.StringIO()):
    import Parameters as P_mod
    init_list = P_mod.return_parameters(Parametrization='Baseline')

init_h = init_list[1]
MrkvArray_recessionUI = init_h['MrkvArray_recessionUI'][0]
J_MICRO = 4
n_macro = MrkvArray_recessionUI.shape[0] // J_MICRO
MICRO_NAMES = {0: 'employed', 1: 'u1Q', 2: 'u2Q', 3: 'noBen'}

def simulate_trace(MrkvArray, initial_state, T, rng):
    state = initial_state
    history = [state]
    for t in range(T):
        probs = MrkvArray[state, :]
        u = rng.random()
        cum = 0.0
        for k, p in enumerate(probs):
            cum += p
            if u <= cum:
                state = k
                break
        history.append(state)
    return history

INITIAL_STATE = 3 * J_MICRO + 0
T_SIM = 12

# Find agents with 4+ benefits
high_benefit_seeds = []
for seed in range(100_000):
    rng = np.random.default_rng(seed=12345 + seed)
    hist = simulate_trace(MrkvArray_recessionUI, INITIAL_STATE, T_SIM, rng)
    micros = [s % J_MICRO for s in hist]
    benefits = sum(1 for m in micros if m in (1, 2))
    # Apply Case 1 strict criteria
    if micros[1] == 1 and all(micros[t] != 0 for t in range(2, 8)):
        if benefits >= 4:
            high_benefit_seeds.append((seed, benefits, hist))

print(f"Found {len(high_benefit_seeds)} Case 1 strict agents with 4+ benefits")
print()
print("Showing first 5:")
for seed, b, hist in high_benefit_seeds[:5]:
    print(f"\nAgent seed={12345+seed}, benefits={b}")
    print(f"{'t':>3} | {'macro':>5} {'micro':>5} | {'name':<12}")
    for t, s in enumerate(hist[:T_SIM]):
        macro, micro = s // J_MICRO, s % J_MICRO
        marker = " ✓" if micro in (1, 2) else "  "
        print(f"{t:>3} | {macro:>5} {micro:>5} | {MICRO_NAMES[micro]:<12}{marker}")
