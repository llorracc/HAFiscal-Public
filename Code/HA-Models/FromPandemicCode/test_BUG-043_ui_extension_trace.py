"""Minimal trace of agent state under recession vs recessionUI scenarios."""
import sys, os, io, contextlib
import numpy as np

sys.path.insert(0, '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode')
sys.argv = ['trace']

# Suppress import noise
with contextlib.redirect_stdout(io.StringIO()):
    import Parameters as P_mod
    init_list = P_mod.return_parameters(Parametrization='Baseline')

# Index 0 is HS (or D) — let's grab any one (Markov structure is the same across edu groups)
init_d = init_list[0]
MrkvArray_recession = init_d['MrkvArray_recession'][0]
MrkvArray_recessionUI = init_d['MrkvArray_recessionUI'][0]
J_micro = 4  # employed, u1Q, u2Q, noBen
n_macro = MrkvArray_recession.shape[0] // J_micro

print(f"MrkvArray_recession   shape: {MrkvArray_recession.shape}")
print(f"MrkvArray_recessionUI shape: {MrkvArray_recessionUI.shape}")
print(f"  → {n_macro} macro states × {J_micro} micro states")
print()

# Trace the AGENT'S MOST LIKELY UNEMPLOYED PATH: at each step, take the
# transition with highest probability AMONG transitions to non-employed states.
MICRO_NAMES = {0: "employed", 1: "u1Q", 2: "u2Q", 3: "noBen"}
INCOMES = {0: "WAGE", 1: "IncUnemp", 2: "IncUnemp", 3: "IncUnempNoBenefits"}

def trace(initial_combined_state, MrkvArray, label, T=12):
    state = initial_combined_state
    print(f"--- {label} ---")
    print(f"{'t':>3} | {'macro':>5} {'micro':>5} | {'state name':<10} | {'income':<22} | {'benefits?':<10}")
    print("-" * 75)
    benefit_count = 0
    for t in range(T):
        macro = state // J_micro
        micro = state % J_micro
        is_benefit = micro in (1, 2)
        marker = "✓" if is_benefit else " "
        if is_benefit:
            benefit_count += 1
        print(f"{t:>3} | {macro:>5} {micro:>5} | {MICRO_NAMES[micro]:<10} | {INCOMES[micro]:<22} | {marker}")
        # Find next state: take argmax of probs to non-employed micro states
        probs = MrkvArray[state, :].copy()
        for k in range(len(probs)):
            if k % J_micro == 0:
                probs[k] = 0  # zero out transitions to employed (we want continued-unemp path)
        if probs.sum() == 0:
            print(f"   (no continued-unemp transition available; agent must become employed)")
            break
        state = int(np.argmax(probs))
    print(f"\n  TOTAL benefits-eligible periods: {benefit_count}")
    return benefit_count

# Per AggFiscalModel.py, recession scenarios shift agents to macro state 3
# (recession with extension just starting). Let's verify what's at that position.
print("Cumulative transition counts at macro state 3 (recession+extension start):")
for src_micro in range(J_micro):
    src = 3 * J_micro + src_micro
    rec_row = MrkvArray_recession[src, :]
    ui_row = MrkvArray_recessionUI[src, :]
    rec_nonzero = [(k, rec_row[k]) for k in range(len(rec_row)) if rec_row[k] > 1e-9]
    ui_nonzero = [(k, ui_row[k]) for k in range(len(ui_row)) if ui_row[k] > 1e-9]
    print(f"  from macro=3, micro={src_micro} ({MICRO_NAMES[src_micro]:>10}):")
    print(f"    rec    transitions: {[(k//J_micro, k%J_micro, round(p,3)) for k,p in rec_nonzero]}")
    print(f"    rec_UI transitions: {[(k//J_micro, k%J_micro, round(p,3)) for k,p in ui_nonzero]}")
print()

# Now trace each starting micro state from macro=3 (recession onset)
print("=" * 78)
print("CASE 1: Agent EMPLOYED at recession onset (becomes unemp during period 0)")
print("=" * 78)
b1_rec = trace(3*J_micro + 0, MrkvArray_recession, "RECESSION (no extension)", T=10)
print()
b1_ui = trace(3*J_micro + 0, MrkvArray_recessionUI, "RECESSION_UI (extension)", T=10)

print("\n" + "=" * 78)
print("CASE 2: Agent at u1Q at recession onset (already unemp, just lost job)")
print("=" * 78)
b2_rec = trace(3*J_micro + 1, MrkvArray_recession, "RECESSION (no extension)", T=10)
print()
b2_ui = trace(3*J_micro + 1, MrkvArray_recessionUI, "RECESSION_UI (extension)", T=10)

print("\n" + "=" * 78)
print("CASE 3: Agent at u2Q at recession onset (unemp 1Q before recession)")
print("=" * 78)
b3_rec = trace(3*J_micro + 2, MrkvArray_recession, "RECESSION (no extension)", T=10)
print()
b3_ui = trace(3*J_micro + 2, MrkvArray_recessionUI, "RECESSION_UI (extension)", T=10)

print("\n" + "=" * 78)
print("EMPIRICAL SUMMARY: max benefits-eligible periods (continued-unemp path)")
print("=" * 78)
print(f"  Case             recession  recessionUI  extra")
print(f"  ----             ---------  -----------  -----")
print(f"  Started employed   {b1_rec:>3}            {b1_ui:>3}        {b1_ui-b1_rec:+d}")
print(f"  Started at u1Q     {b2_rec:>3}            {b2_ui:>3}        {b2_ui-b2_rec:+d}")
print(f"  Started at u2Q     {b3_rec:>3}            {b3_ui:>3}        {b3_ui-b3_rec:+d}")
