"""Section-5 figure family (live engine) — candidate-routed writes.

Same figures, filenames, and write order as the frozen GE monolith:
the across-horizon multiplier lines land in HANK_IRFs_w_splurge.* first
and are then OVERWRITTEN by the three-panel IRF figure (deliberate
historical behavior — the shipped file is the 3-panel version); the
per-policy IRF and multiplier figures go through generated_output's
candidate routing (QE freeze) into FromPandemicCode/Figures/.
"""
import os

import numpy as np

from .common import FPC_DIR, ensure_paths

ensure_paths()

import matplotlib.pyplot as plt  # noqa: E402

figures_dir = os.path.join(FPC_DIR, 'Figures')


def _routed_writes(canonical_rel, exts=("jpg", "pdf", "svg", "png")):
    from generated_output import output_path, lock_axes_for
    # Same published-axes lock the FromPandemicCode helpers apply (HAFISCAL_FIG_AXES_LOCK,
    # default on); it also refreshes Figures/axes_lock_report.json, which UPDATES.md's axes
    # note reads. A bare savefig left that report describing whatever last locked the figure.
    lock_axes_for(f"{canonical_rel}.pdf", plt.gcf())
    for ext in exts:
        plt.savefig(output_path(f"{canonical_rel}.{ext}"))
    plt.show(block=False)


def render_across_horizon(multipliers_transfers, multipliers_UI_extensions,
                          multipliers_tax_cut, horizon_length):
    plt.plot(np.arange(horizon_length) + 1, multipliers_transfers,
             label='Stimulus Check', color='green')
    plt.plot(np.arange(horizon_length) + 1, multipliers_UI_extensions,
             label='UI extensions', color='blue')
    plt.plot(np.arange(horizon_length) + 1, multipliers_tax_cut,
             label='Tax cut', color='red')
    plt.legend(loc='lower right')
    plt.ylabel('C mulitpliers')
    plt.xlabel('quarters $t$')
    plt.xlim(.5, 12.5)
    plt.title('Consumption Multipliers across horizon')
    _routed_writes("Figures/HANK_IRFs_w_splurge")


def plot_consumption_irfs_three_experiments(irf_UI1, irf_UI2, irf_UI3,
                                            irf_SC1, irf_SC2, irf_SC3,
                                            irf_TC1, irf_TC2, irf_TC3, C_ss):
    green = 'darkorange'
    red = 'red'

    Length = 12
    fontsize = 10
    width = 2
    label_size = 8
    legend_size = 8
    ticksize = 8
    fig, axs = plt.subplots(1, 3, figsize=(10, 3))

    # The fixed-nominal-rate (peg) series is OPTIONAL: pass None to omit it. Owner ruling
    # 2026-09-05: the peg is dropped from the revision's figures -- the regime is nearly
    # indeterminate (fiscal policy is nearly passive too; the multiplier has a pole in one
    # Jacobian entry, conclusions_private/2026-09-01_the-peg-multiplier-has-a-pole-...md) --
    # and the Taylor rule with 0.7 persistence is shown instead. The y-axis is set from the
    # arms actually drawn (it used to be set from the peg, whose impact-date oscillation
    # inflated it).
    panels = ((0, "Stimulus Check", irf_SC1, irf_SC2, irf_SC3),
              (1, "UI Extension", irf_UI1, irf_UI2, irf_UI3),
              (2, "Tax Cut", irf_TC1, irf_TC2, irf_TC3))
    y_max = max(max(100 * irf['C'][:Length] / C_ss) for _, _, *arms in panels for irf in arms if irf is not None) * 1.05
    for i in range(3):
        axs[i].set_ylim(0, y_max)

    for i, title, irf1, irf2, irf3 in panels:
        axs[i].plot(100 * irf1['C'][:Length] / C_ss, linewidth=width, label="Active Taylor Rule")
        if irf2 is not None:
            axs[i].plot(100 * irf2['C'][:Length] / C_ss, linewidth=width, label="Fixed Nominal Rate", linestyle='--', color=green)
        axs[i].plot(100 * irf3['C'][:Length] / C_ss, linewidth=width, label="Fixed Real ", linestyle=':', color=red)
        axs[i].set_title(title, fontdict={'fontsize': fontsize})
    # Owner rule 2026-09-05: every generated figure carries a legend naming what each
    # colour is -- on every panel, not only the first.
    for i in range(3):
        axs[i].legend(prop={'size': legend_size})

    for i in range(3):
        axs[i].plot(np.zeros(Length), 'k')
        axs[i].tick_params(axis='both', labelsize=ticksize)
        axs[i].set_ylabel('% consumption deviation', fontsize=label_size)
        axs[i].set_xlabel('Quarters', fontsize=label_size)
        axs[i].locator_params(axis='both', nbins=4)

    fig.tight_layout()
    _routed_writes("Figures/HANK_IRFs_w_splurge", exts=("pdf", "jpg", "png", "svg"))


def plot_consumption_irf(irf1, irf2, irf3, C_ss, y_max, filename, legend=False):
    green = 'darkorange'
    red = 'red'

    Length = 12
    plt.figure(figsize=(4, 4))
    x_axis = np.arange(1, Length + 1)

    plt.plot(x_axis, 100 * irf1['C'][:Length] / C_ss, label="Active Taylor Rule")
    if irf2 is not None:   # the peg; None = omitted (owner ruling 2026-09-05, see above)
        plt.plot(x_axis, 100 * irf2['C'][:Length] / C_ss, label="Fixed Nominal Rate", linestyle='--', color=green)
    plt.plot(x_axis, 100 * irf3['C'][:Length] / C_ss, label="Fixed Real", linestyle=':', color=red)

    plt.xticks(np.arange(min(x_axis), max(x_axis) + 1, 1.0))
    plt.xlabel('quarter')
    plt.ylim(0, y_max)
    plt.legend(loc='best')   # owner rule 2026-09-05: a legend on every generated figure
    if legend:   # the argument now only places the y-label, as in the published layout
        plt.ylabel('% consumption deviation')

    if filename:
        from generated_output import output_name, lock_axes_for
        lock_axes_for(f"{filename}.pdf", plt.gcf())   # published-axes lock + report (see _routed_writes)
        routed = output_name(filename)
        for ext in ("pdf", "png", "svg", "jpg"):
            plt.savefig(os.path.join(figures_dir, f"{routed}.{ext}"))
        plt.show(block=False)


def plot_consumption_multipliers(multiplier1, multiplier2, multiplier3, y_max,
                                 filename, legend=False):
    green = 'darkorange'
    red = 'red'

    Length = 12
    plt.figure(figsize=(4, 4))
    x_axis = np.arange(1, Length + 1)

    plt.plot(x_axis, multiplier1[0:Length], label="Active Taylor Rule")
    if multiplier2 is not None:   # the peg; None = omitted (owner ruling 2026-09-05)
        plt.plot(x_axis, multiplier2[0:Length], label="Fixed Nominal Rate", linestyle='--', color=green)
    plt.plot(x_axis, multiplier3[0:Length], label="Fixed Real", linestyle=':', color=red)

    plt.xticks(np.arange(min(x_axis), max(x_axis) + 1, 1.0))
    plt.xlabel('quarter')
    plt.ylim(0, y_max)
    plt.legend(loc='best')   # owner rule 2026-09-05: a legend on every generated figure (`legend` kept for the signature)

    if filename:
        from generated_output import output_name, lock_axes_for
        lock_axes_for(f"{filename}.pdf", plt.gcf())   # published-axes lock + report (see _routed_writes)
        routed = output_name(filename)
        for ext in ("pdf", "png", "svg", "jpg"):
            plt.savefig(os.path.join(figures_dir, f"{routed}.{ext}"))
        plt.show(block=False)
