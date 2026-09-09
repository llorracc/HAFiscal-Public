"""
Updated plotting functions for HANK-SAM dashboard.
Modified to show only "Deviation from baseline" (standard Taylor rule).
Includes two-scenario comparison functions.
"""

import numpy as np
import matplotlib.pyplot as plt

# Import horizon_length and C_ss from hafiscal if needed
horizon_length = 20  # Default value
C_ss = 0.6910496136078721  # From hank_sam.py


def plot_multipliers_three_experiments(
    multipliers_transfers,
    multipliers_transfers_fixed_nominal_rate,
    multipliers_transfers_fixed_real_rate,
    multipliers_UI_extend,
    multipliers_UI_extensions_fixed_nominal_rate,
    multipliers_UI_extensions_fixed_real_rate,
    multipliers_tax_cut,
    multipliers_tax_cut_fixed_nominal_rate,
    multipliers_tax_cut_fixed_real_rate,
    fig_and_axes=None,
):
    """
    Plot fiscal multipliers for three experiments showing only deviation from baseline.
    
    Args:
        multipliers_* : Arrays of multiplier values for each policy/regime
        fig_and_axes: Optional tuple of (fig, axes) to draw on. If None, creates new figure.
    
    Returns:
        fig: The matplotlib figure object
    """
    # Dashboard control: use provided figure/axes or create new
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
    else:
        fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    
    # Use consistent colors
    baseline_color = "#1f77b4"  # Blue for baseline
    
    Length = len(multipliers_transfers_fixed_nominal_rate) + 1
    fontsize = 12
    width = 2.5
    label_size = 12  # Increased from 10
    legend_size = 10
    ticksize = 11  # Increased from 9 to 11
    
    # Determine common y-axis limits across ALL multipliers
    all_max_values = [
        max(multipliers_transfers[:horizon_length]),
        max(multipliers_UI_extend[:horizon_length]),
        max(multipliers_tax_cut[:horizon_length])
    ]
    y_max = max(all_max_values) * 1.2
    y_min = -0.2
    
    # Apply same y-axis limits to all subplots
    for i in range(3):
        axs[i].set_ylim(y_min, y_max)
    
    # Plot Stimulus Check (middle panel -> first panel)
    axs[0].plot(
        np.arange(horizon_length) + 1,
        multipliers_transfers[:horizon_length],
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[0].set_title("Stimulus Check", fontdict={"fontsize": fontsize})
    axs[0].legend(prop={"size": legend_size}, loc="upper right")
    
    # Plot UI Extension (first panel -> middle panel)
    axs[1].plot(
        np.arange(horizon_length) + 1,
        multipliers_UI_extend[:horizon_length],
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[1].set_title("UI Extension", fontdict={"fontsize": fontsize})
    
    # Plot Tax Cut (last panel)
    axs[2].plot(
        np.arange(horizon_length) + 1,
        multipliers_tax_cut[:horizon_length],
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[2].set_title("Tax Cut", fontdict={"fontsize": fontsize})
    
    # Format all axes
    for i in range(3):
        axs[i].axhline(y=0, color="black", linewidth=0.8, alpha=0.7)
        axs[i].tick_params(axis="both", labelsize=ticksize)
        axs[i].set_ylabel("Consumption Multiplier", fontsize=label_size, labelpad=10)
        axs[i].set_xlabel("Time (Quarters)", fontsize=label_size, labelpad=10)
        axs[i].locator_params(axis="both", nbins=6)
        axs[i].grid(alpha=0.3, linewidth=0.5)
        axs[i].set_xlim(0.5, 12.5)  # Focus on first 3 years
    
    # All axes now show y-labels since we removed sharey=True
    # No need to remove labels anymore
    
    plt.tight_layout()
    return fig


def plot_consumption_irfs_three_experiments(
    irf_UI1, irf_UI2, irf_UI3, irf_SC1, irf_SC2, irf_SC3, irf_TC1, irf_TC2, irf_TC3,
    fig_and_axes=None,
):
    """
    Plot consumption IRFs for three experiments showing only deviation from baseline.
    
    Args:
        irf_* : IRF dictionaries for each policy/regime combination
        fig_and_axes: Optional tuple of (fig, axes) to draw on.
    
    Returns:
        fig: The matplotlib figure object
    """
    # Dashboard control: use provided figure/axes or create new
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
    else:
        fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    
    baseline_color = "#1f77b4"  # Blue for baseline
    
    Length = 12  # 3 years
    fontsize = 12
    width = 2.5
    label_size = 12  # Increased from 10
    legend_size = 10
    ticksize = 11  # Increased from 9 to 11
    
    # Determine common y-axis limits across ALL IRFs
    all_max_values = [
        max(100 * irf_SC1["C"][:Length] / C_ss),
        max(100 * irf_UI1["C"][:Length] / C_ss),
        max(100 * irf_TC1["C"][:Length] / C_ss)
    ]
    y_max = max(all_max_values) * 1.1
    y_min = -0.2
    
    # Apply same y-axis limits to all subplots
    for i in range(3):
        axs[i].set_ylim(y_min, y_max)
    
    # Plot Stimulus Check
    axs[0].plot(
        np.arange(Length),
        100 * irf_SC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[0].set_title("Stimulus Check", fontdict={"fontsize": fontsize})
    axs[0].legend(prop={"size": legend_size}, loc="upper right")
    
    # Plot UI Extension
    axs[1].plot(
        np.arange(Length),
        100 * irf_UI1["C"][:Length] / C_ss,
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[1].set_title("UI Extension", fontdict={"fontsize": fontsize})
    
    # Plot Tax Cut
    axs[2].plot(
        np.arange(Length),
        100 * irf_TC1["C"][:Length] / C_ss,
        linewidth=width,
        label="Deviation from baseline",
        color=baseline_color,
    )
    axs[2].set_title("Tax Cut", fontdict={"fontsize": fontsize})
    
    # Format all axes
    for i in range(3):
        axs[i].axhline(y=0, color="black", linewidth=0.8, alpha=0.7)
        axs[i].tick_params(axis="both", labelsize=ticksize)
        axs[i].set_ylabel("Consumption Response (%)", fontsize=label_size, labelpad=10)
        axs[i].set_xlabel("Time (Quarters)", fontsize=label_size, labelpad=10)
        axs[i].locator_params(axis="both", nbins=6)
        axs[i].grid(alpha=0.3, linewidth=0.5)
    
    # All axes now show y-labels since we removed sharey=True
    # No need to remove labels anymore
    
    plt.tight_layout()
    return fig


def plot_scenario_comparison_multipliers(mult1, mult2, fig_and_axes=None):
    """Plot multipliers comparing two scenarios."""
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
    else:
        fig, axs = plt.subplots(1, 3, figsize=(14, 5))
    
    # Colors and markers for scenarios
    colors = {'s1': '#3b82f6', 's2': '#ec4899'}
    markers = {'s1': 'o', 's2': '^'}
    
    policies = ['Stimulus Check', 'UI Extension', 'Tax Cut']
    mult_keys = ['transfers', 'UI_extend', 'tax_cut']
    
    horizon_length = 20
    x_axis = np.arange(horizon_length) + 1
    
    # Determine common y-axis limits across all policies and both scenarios
    all_max_values = []
    for key in mult_keys:
        all_max_values.extend([
            max(mult1[key][:horizon_length]),
            max(mult2[key][:horizon_length])
        ])
    y_max = max(all_max_values) * 1.2
    y_min = -0.2
    
    # Plot each policy type
    for i, (policy, key) in enumerate(zip(policies, mult_keys)):
        ax = axs[i]
        
        # Plot both scenarios
        ax.plot(x_axis, mult1[key][:horizon_length], 
                color=colors['s1'], linewidth=2.5, 
                marker=markers['s1'], markersize=6, markevery=2,
                label='Scenario 1', alpha=0.9)
        
        ax.plot(x_axis, mult2[key][:horizon_length], 
                color=colors['s2'], linewidth=2.5, linestyle='--',
                marker=markers['s2'], markersize=6, markevery=2,
                label='Scenario 2', alpha=0.9)
        
        # Apply common y-axis limits
        ax.set_ylim(y_min, y_max)
        
        # Styling
        ax.set_title(policy, fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel('Time (Quarters)', fontsize=12)
        ax.set_ylabel('Consumption Multiplier', fontsize=13)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_xlim(0.5, 12.5)
        
        # Add zero line
        ax.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)
        
        # Legend inside each subplot
        ax.legend(loc='upper right', frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    return fig


def plot_scenario_comparison_irfs(irfs1, irfs2, fig_and_axes=None):
    """Plot consumption IRFs comparing two scenarios."""
    if fig_and_axes is not None:
        fig, axs = fig_and_axes
    else:
        fig, axs = plt.subplots(1, 3, figsize=(14, 5))
    
    # Colors and markers for scenarios
    colors = {'s1': '#3b82f6', 's2': '#ec4899'}
    markers = {'s1': 'o', 's2': '^'}
    
    policies = ['Stimulus Check', 'UI Extension', 'Tax Cut']
    irf_keys = ['transfer', 'UI_extend', 'tau']
    
    Length = 12
    x_axis = np.arange(Length)
    
    # Determine common y-axis limits across all policies and both scenarios
    all_max_values = []
    for key in irf_keys:
        all_max_values.extend([
            max(100 * irfs1[key]['C'][:Length] / C_ss),
            max(100 * irfs2[key]['C'][:Length] / C_ss)
        ])
    y_max = max(all_max_values) * 1.1
    y_min = -0.2
    
    # Plot each policy type
    for i, (policy, key) in enumerate(zip(policies, irf_keys)):
        ax = axs[i]
        
        # Plot both scenarios
        ax.plot(x_axis, 100 * irfs1[key]['C'][:Length] / C_ss,
                color=colors['s1'], linewidth=2.5,
                marker=markers['s1'], markersize=6, markevery=2,
                label='Scenario 1', alpha=0.9)
        
        ax.plot(x_axis, 100 * irfs2[key]['C'][:Length] / C_ss,
                color=colors['s2'], linewidth=2.5, linestyle='--',
                marker=markers['s2'], markersize=6, markevery=2,
                label='Scenario 2', alpha=0.9)
        
        # Apply common y-axis limits
        ax.set_ylim(y_min, y_max)
        
        # Styling
        ax.set_title(policy, fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel('Time (Quarters)', fontsize=12)
        ax.set_ylabel('Consumption Response (%)', fontsize=13)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Add zero line
        ax.axhline(y=0, color='black', linewidth=0.8, alpha=0.5)
        
        # Legend inside each subplot
        ax.legend(loc='upper right', frameon=True, fancybox=True, shadow=True)
    
    plt.tight_layout()
    return fig