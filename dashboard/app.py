# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
# Import branding (header will be integrated into the dashboard)
from IPython.display import HTML, display
from branding.econ_ark_style import HEADER_HTML

# Note: Header is now integrated into the dashboard layout

# %%
# HANK-SAM Model Interactive Dashboard.
# Author: Alan Lujan <alujan@jhu.edu>

# This Voila dashboard allows interactive exploration of the HANK-SAM model's
# fiscal multipliers under different monetary and fiscal policy parameters.

# Import required packages
import ipywidgets as widgets
from IPython.display import clear_output, display
from ipywidgets import HTML, HBox, Layout, VBox
import matplotlib.pyplot as plt

# Import our refactored model module and branding
import hank_sam as hs
from branding.econ_ark_style import (
    ARK_BLUE, ARK_LIGHTBLUE, ARK_ORANGE, ARK_GREEN,
    ARK_SLATE_DK, ARK_SLATE_LT, ARK_GREY, ARK_GRID,
    ARK_PANEL, ARK_PANEL_LIGHT, ARK_GRID_SOFT, ARK_SPINE,
    ARK_TEXT, MATPLOTLIB_STYLE, DASHBOARD_CSS, tidy_legend
)

# Configure Matplotlib with Econ-ARK branding
plt.rcParams.update(MATPLOTLIB_STYLE)

# Apply global dashboard styles with custom additions
custom_css = DASHBOARD_CSS + """
<style>
    /* Professional dashboard styling inspired by modern analytics platforms */
    
    /* Section headings - consistent professional styling */
    .section-heading {
        font-weight: 600 !important;
        color: #1a202c !important;
        font-size: 0.875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
        margin-bottom: 1rem !important;
        padding-left: 0 !important;
        border: none !important;
    }
    
    /* Widget containers with subtle depth */
    .parameter-card {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.2s ease !important;
    }
    
    .parameter-card:hover {
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07) !important;
    }
    
    /* Primary controls emphasis */
    .primary-controls {
        background: #ffffff !important;
        border: 2px solid var(--ark-blue) !important;
        box-shadow: 0 4px 6px rgba(0, 91, 143, 0.1) !important;
    }
    
    /* Secondary controls styling */
    .secondary-controls {
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
    }
    
    /* Enhanced slider styling - professional look */
    .widget-slider {
        margin: 1.2em 0 !important;
    }
    
    .widget-label {
        font-weight: 500 !important;
        color: #2d3748 !important;
        font-size: 0.875rem !important;
        margin-bottom: 0.5em !important;
    }
    
    .widget-readout {
        background: #edf2f7 !important;
        color: var(--ark-blue) !important;
        padding: 0.25em 0.75em !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        min-width: 4em !important;
        text-align: center !important;
        border: 1px solid #cbd5e0 !important;
    }
    
    /* Modern slider track */
    .ui-slider {
        background: #e2e8f0 !important;
        height: 4px !important;
        border-radius: 2px !important;
        position: relative !important;
    }
    
    .ui-slider-range {
        background: var(--ark-blue) !important;
        height: 4px !important;
        border-radius: 2px !important;
    }
    
    .ui-slider-handle {
        background: #ffffff !important;
        border: 2px solid var(--ark-blue) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        width: 20px !important;
        height: 20px !important;
        border-radius: 50% !important;
        top: -8px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
    }
    
    .ui-slider-handle:hover {
        transform: scale(1.1) !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.15) !important;
    }
    
    .ui-slider-handle:active {
        transform: scale(0.95) !important;
    }
    
    /* Professional button styling */
    .widget-button {
        background: var(--ark-blue) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75em 1.5em !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
        box-shadow: 0 2px 4px rgba(0, 91, 143, 0.2) !important;
        transition: all 0.2s ease !important;
    }
    
    .widget-button:hover:not(:disabled) {
        background: #004a73 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(0, 91, 143, 0.3) !important;
    }
    
    .widget-button:active:not(:disabled) {
        transform: translateY(0) !important;
    }
    
    .widget-button:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }
    
    /* Status indicator styling */
    .status-container {
        background: #f7fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        padding: 0.75em 1em !important;
        margin-top: 1em !important;
    }
    
    /* Clean sidebar styling */
    .sidebar-container {
        background: #fafbfc !important;
        border-right: 1px solid #e2e8f0 !important;
    }
    
    /* Override any conflicting h2 styles that might be causing the line */
    h2.ark-h2::after {
        display: none !important;
    }
</style>
"""
# Note: CSS will be injected into the dashboard widget, not displayed separately

def create_heading(text, level=2, style_class=""):
    """Create a heading widget with consistent styling."""
    tag = f"h{level}"
    class_str = f"ark-h{level} {style_class}".strip()
    return HTML(f"<{tag} class='{class_str}'>{text}</{tag}>")


# %%
# Create style for sliders - optimized for compact layout
style = {
    "description_width": "45%",  # Relative description width
    "description_font_size": "0.9rem",  # Match ark-label class
    "description_font_weight": "500",  # Match ark-label class
    "description_color": ARK_TEXT,  # Use brand text color
}
slider_layout = Layout(width="90%")  # Wider relative width per brand guide

# %%
# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1: CREATE PARAMETER WIDGETS
# ═════════════════════════════════════════════════════════════════════════════

# Monetary Policy Parameters
phi_pi_widget = widgets.FloatSlider(
    value=1.5,
    min=1.0,
    max=3.0,
    step=0.1,
    description="Taylor rule inflation weight (φπ):",
    style=style,
    layout=slider_layout,
    continuous_update=False,
    readout=True,
    readout_format=".2f",
)

# %%
phi_y_widget = widgets.FloatSlider(
    value=0.0,
    min=0.0,
    max=1.0,
    step=0.05,
    description="Taylor rule output weight (φy):",
    style=style,
    layout=slider_layout,
    continuous_update=False,
    readout=True,
    readout_format=".2f",
)

# %%
# Fixed parameters as per relabel.md
# rho_r = 0.0 (Taylor rule inertia)
# kappa_p = 0.065 (was 0.06191950464396284)
# real_wage_rigidity = 0.95 (was 0.837)

# Fiscal and Structural Parameters
phi_b_widget = widgets.FloatSlider(
    value=0.015,
    min=0.0,
    max=0.1,
    step=0.005,
    description="Fiscal adjustment (φb):",
    style=style,
    layout=slider_layout,
    continuous_update=False,
    readout=True,
    readout_format=".3f",
)

# Policy Duration Parameters
ui_extension_widget = widgets.IntSlider(
    value=4,
    min=1,
    max=12,
    step=1,
    description="UI extension (quarters):",
    style=style,
    layout=slider_layout,
    continuous_update=False,
    readout=True,
)

tax_cut_widget = widgets.IntSlider(
    value=8,
    min=1,
    max=16,
    step=1,
    description="Tax cut (quarters):",
    style=style,
    layout=slider_layout,
    continuous_update=False,
    readout=True,
)

# %%
# Create a status panel with button and progress label
run_button = widgets.Button(
    description="Run Simulation",
    layout=Layout(width="100%", height="40px"),
    style={"button_color": ARK_BLUE, "font_weight": "600"},
)

# Create initial status HTML with Econ-ARK styling
initial_status_html = f"""
<div class="status-container" style="display: flex; align-items: center; justify-content: center; gap: 0.75em;">
    <div style="width: 8px; height: 8px; border-radius: 50%; 
                background: {ARK_GREY};">
    </div>
    <span style="color: {ARK_SLATE_DK}; font-size: 0.875rem;">Ready to run simulation</span>
</div>
"""

progress_label = widgets.HTML(
    value=initial_status_html,
    layout=Layout(
        width="100%", 
        margin="0.5em 0 0 0"
    )
)

# Create the status panel
status_panel = widgets.VBox(
    [run_button, progress_label],
    layout=Layout(
        width="100%",
        padding="0"
    )
)

# %%
# Create placeholder message for plots
placeholder_html = f"""
<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; 
            background-color:{ARK_PANEL}; border-radius:8px; padding:1.5em;
            height:250px;">
    <div style="font-size:1.1rem; color:{ARK_SLATE_DK}; margin-bottom:0.75em;">
        ⚡ Run Simulation to Generate Plots
    </div>
    <div style="font-size:0.9rem; color:{ARK_GREY}; text-align:center; max-width:300px;">
        Adjust parameters and click 'Run Simulation' to explore fiscal policy scenarios.
    </div>
</div>
"""

# Output widgets for truly responsive figures - adaptive to container size
fig_output_layout = Layout(
    width="100%",
    max_width="1400px",  # Maximum width to prevent excessive stretching
    height="auto",  # Let height adjust to content
    min_height="350px",  # Slightly taller minimum
    background_color=ARK_PANEL,  # Light background for plots
    border_radius="8px",  # Rounded corners
    padding="2em 1.5em",  # More padding all around
    margin="1em auto",  # More vertical margin, auto horizontal
    overflow="visible",  # Allow content to be visible
    display="flex",  # Use flexbox
    align_items="center",  # Center vertically
    justify_content="center",  # Center horizontally
)

# Create both outputs with the same layout
fig1_output = widgets.Output(layout=fig_output_layout)
fig2_output = widgets.Output(layout=fig_output_layout)

# Initialize outputs with placeholder message
with fig1_output:
    display(HTML(placeholder_html))
with fig2_output:
    display(HTML(placeholder_html))


# %%
def update_status(msg, is_final=False, is_error=False):
    """Create status HTML with consistent styling."""
    if is_error:
        dot_color = ARK_ORANGE
        animate = ""
    elif is_final:
        dot_color = ARK_GREEN
        animate = ""
        msg = "Complete"  # Override message for completion
    else:
        dot_color = ARK_ORANGE
        animate = "animation: pulse 1.2s ease-in-out infinite;"
        msg = "Solving..."  # Override all intermediate messages
        
    return f"""
    <div style="display: flex; align-items: center; justify-content: center; gap: 0.8em;">
        <div style="width: 12px; height: 12px; border-radius: 50%; 
                    background: {dot_color}; {animate}">
        </div>
        <span style="color: {ARK_SLATE_DK}; font-weight: 500;">
            {msg}
        </span>
    </div>
    <style>
        @keyframes pulse {{
            0% {{ transform: scale(0.95); opacity: 0.7; }}
            50% {{ transform: scale(1.05); opacity: 1; }}
            100% {{ transform: scale(0.95); opacity: 0.7; }}
        }}
    </style>
    """



# %%
def update_plots(*args) -> None:
    """Run the unified academic figure for the dashboard with enhanced feedback."""
    # Disable button and show solving status
    run_button.disabled = True
    progress_label.value = update_status("Solving...")

    try:
        # Get parameter values
        params = {
            "phi_pi": phi_pi_widget.value,
            "phi_y": phi_y_widget.value,
            "rho_r": 0.0,  # Fixed value (Taylor rule inertia)
            "kappa_p": 0.065,  # Fixed value (closer to original 0.06191950464396284)
            "phi_b": phi_b_widget.value,
            "real_wage_rigidity": 0.95,  # Fixed value as per relabel.md
            "UI_extension_length": ui_extension_widget.value,
            "tax_cut_length": tax_cut_widget.value,
        }

        # Run all experiments with consistent status
        def update_computation_status(msg):
            # Always show "Solving..." with the pulsing dot
            progress_label.value = update_status("Solving...")
            
        results = hs.compute_fiscal_multipliers(
            status_callback=update_computation_status,
            **params
        )
        multipliers = results["multipliers"]
        irfs = results["irfs"]

        # Create figures with dashboard control over canvas
        import matplotlib.pyplot as plt

        # Figure 1: Fiscal Multipliers - guaranteed fit sizing
        fig1_output.clear_output(wait=True)
        with fig1_output:
            # Create figure that fits the container with matching background
            fig1, axes1 = plt.subplots(
                1, 3, figsize=(14, 4.2), sharey=True,  # Increased height
                facecolor=ARK_PANEL  # Set figure background to match container
            )
            fig1.patch.set_alpha(1.0)  # Make background fully opaque
            # Adjust subplot parameters for better spacing
            plt.subplots_adjust(
                left=0.1,      # Left margin
                right=0.95,    # Right margin
                bottom=0.2,    # More space for x-labels
                top=0.95,      # Top margin
                wspace=0.25    # Space between subplots
            )

            fig1 = hs.plot_multipliers_three_experiments(
                multipliers["transfers"],
                multipliers["transfers_fixed_nominal"],
                multipliers["transfers_fixed_real"],
                multipliers["UI_extend"],
                multipliers["UI_extend_fixed_nominal"],
                multipliers["UI_extend_fixed_real"],
                multipliers["tax_cut"],
                multipliers["tax_cut_fixed_nominal"],
                multipliers["tax_cut_fixed_real"],
                fig_and_axes=(fig1, axes1),
            )
            if fig1 is not None:
                display(fig1)
                plt.close(fig1)

        # Figure 2: Consumption IRFs - guaranteed fit sizing
        fig2_output.clear_output(wait=True)
        with fig2_output:
            # Create figure that fits the container with matching background
            fig2, axes2 = plt.subplots(
                1, 3, figsize=(14, 4.2), sharey=True,  # Increased height
                facecolor=ARK_PANEL  # Set figure background to match container
            )
            fig2.patch.set_alpha(1.0)  # Make background fully opaque
            # Adjust subplot parameters for better spacing
            plt.subplots_adjust(
                left=0.1,      # Left margin
                right=0.95,    # Right margin
                bottom=0.2,    # More space for x-labels
                top=0.95,      # Top margin
                wspace=0.25    # Space between subplots
            )

            fig2 = hs.plot_consumption_irfs_three_experiments(
                irfs["UI_extend"],
                irfs["UI_extend_fixed_nominal"],
                irfs["UI_extend_fixed_real"],
                irfs["transfer"],
                irfs["transfer_fixed_nominal"],
                irfs["transfer_fixed_real"],
                irfs["tau"],
                irfs["tau_fixed_nominal"],
                irfs["tau_fixed_real"],
                fig_and_axes=(fig2, axes2),
            )
            if fig2 is not None:
                display(fig2)
                plt.close(fig2)

        # Update summary statistics
        stimulus_mult_1yr = multipliers["transfers"][3]  # 1-year (4 quarters)
        ui_mult_1yr = multipliers["UI_extend"][3]
        tax_mult_1yr = multipliers["tax_cut"][3]

        summary_html = f"""
        <div style='display: flex; flex-direction: column; gap: 0.4em;
                    margin: 0; padding: 1em; background-color: {ARK_PANEL}; border-radius: 8px;
                    color: {ARK_SLATE_DK}; font-size: 0.9rem; line-height: 1.2;'>
            <div>Stimulus Check: <span style='color: {ARK_BLUE}; font-weight: 600; margin-left: 0.5em;'>{stimulus_mult_1yr:.2f}</span></div>
            <div>UI Extension: <span style='color: {ARK_BLUE}; font-weight: 600; margin-left: 0.5em;'>{ui_mult_1yr:.2f}</span></div>
            <div>Tax Cut: <span style='color: {ARK_BLUE}; font-weight: 600; margin-left: 0.5em;'>{tax_mult_1yr:.2f}</span></div>
        </div>
        """

        # Update the summary section
        summary_section.children[1].value = summary_html

        # Show completion status
        progress_label.value = update_status("Complete", is_final=True)
        run_button.disabled = False

    except Exception as e:
        # Show error status
        progress_label.value = update_status(f"Error: {str(e)}", is_error=True)
        run_button.disabled = False
        for output in [fig1_output, fig2_output]:
            with output:
                clear_output(wait=True)


# %%
# Connect button to update function
run_button.on_click(update_plots)

# %%
# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3: CREATE DASHBOARD LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

# Policy Duration (primary controls)
policy_duration_group = VBox(
    [ui_extension_widget, tax_cut_widget],
    layout=Layout(
        padding='1.5rem',
        background='#ffffff',
        border='2px solid ' + ARK_BLUE,
        border_radius='8px',
        width='100%',
        margin='0 0 1.5rem 0'
    )
)
policy_duration_group.add_class("parameter-card")
policy_duration_group.add_class("primary-controls")

# Monetary and Fiscal Policy Settings (secondary controls)
monetary_fiscal_group = VBox(
    [phi_pi_widget, phi_y_widget, phi_b_widget],
    layout=Layout(
        padding='1.5rem',
        background='#f8fafc',
        border='1px solid #e2e8f0',
        border_radius='8px',
        width='100%',
        margin='0 0 1.5rem 0'
    )
)
monetary_fiscal_group.add_class("parameter-card")
monetary_fiscal_group.add_class("secondary-controls")

# Create section headings with consistent styling
policy_duration_heading = HTML("""
<h3 class="section-heading">Policy Duration</h3>
""")

settings_heading = HTML("""
<h3 class="section-heading">Monetary and Fiscal Policy Settings</h3>
""")

simulation_heading = HTML("""
<h3 class="section-heading">Simulation Control</h3>
""")

# SIDEBAR - professional layout (removed redundant "Model Parameters" heading)
options_panel = VBox(
    [
        policy_duration_heading,
        policy_duration_group,
        settings_heading,
        monetary_fiscal_group,
        simulation_heading,
        status_panel
    ],
    layout=Layout(
        padding="2rem 1.5rem",
        width="100%",
        height="auto",
        min_height="700px",
        overflow_y="visible",
        overflow_x="hidden",
    ),
)
options_panel.add_class("sidebar-container")

# %%
# MAIN CONTENT - Two figure panels with fixed layout
fig1_panel = VBox(
    [
        create_heading("Fiscal Multipliers by Policy Type", 2, "lightblue"),
        fig1_output,
    ],
    layout=Layout(
        border="none",
        padding="0",
        margin="0 0 2em 0",  # Spacing between plots
        width="100%",
        height="auto",  # Let height adjust to content
        min_height="400px",  # Minimum height
        max_height="500px",  # Maximum height to prevent overflow
        overflow="hidden",  # Prevent overflow
    ),
)

fig2_panel = VBox(
    [
        create_heading("Consumption Response Functions", 2, "lightblue"),
        fig2_output,
    ],
    layout=Layout(
        border="none",
        padding="0",
        margin="0",
        width="100%",
        height="auto",  # Let height adjust to content
        min_height="400px",  # Minimum height
        max_height="500px",  # Maximum height to prevent overflow
        overflow="hidden",  # Prevent overflow
    ),
)

# Create introduction section with H1 title and larger body text
intro_section = VBox(
    [
        create_heading("HANK-SAM Fiscal Policy Analysis", 1),
        HTML(
            "<div style='margin: 0; padding: 0;'>"
            "<p class='ark-body' style='margin: 0 0 1em 0;'>"
            "This dashboard explores fiscal multipliers in a Heterogeneous Agent New Keynesian (HANK) model with Search and Matching frictions. "
            "To capture the distributional effects of fiscal policy, the model features  households with heterogeneous preferences facing ideosyncratic income risk, unemployment dynamics, and endogenous job creation.</p>"
            "<p class='ark-body' style='margin: 0 0 1em 0;'>"
            #"Adjust the monetary and fiscal parameters below to explore how different policy regimes affect consumption multipliers. "
            #"Compare results across three fiscal policies: stimulus checks, UI extensions, and tax cuts under standard Taylor rule, fixed nominal rate, and fixed real rate scenarios.</p>"
            "<p class='ark-body' style='margin: 0 0 1em 0; font-style: italic; opacity: 0.9;'>"
            "Key insight: UI extensions typically generate the highest multipliers due to targeting unemployed households with high marginal propensities to consume.</p>"
            "</div>"
        ),
    ],
    layout=Layout(
        width="100%",
        padding="0",
        margin="0 0 2em 0",
        min_height="250px",  # Minimum height
        height="auto",  # Let it grow as needed
        overflow="visible",  # Allow content to be fully visible
    ),
)

# Create summary statistics section (will be populated by simulation results)
summary_section = VBox(
    [
        create_heading("Key Multipliers (1-Year Horizon)", 2, "lightblue"),  # Same style as other headings
        HTML(
            "<div id='summary-stats' style='margin: 0.5em 0 0 0; padding: 1.5em; "
            f"background-color: {ARK_PANEL}; border-radius: 8px; font-size: 1rem; text-align: center;' class='ark-label'>"
            "Run simulation to view key results...</div>"
        ),
    ],
    layout=Layout(
        width="100%",
        padding="0",
        margin="0 0 3em 0",  # More spacing after summary
        height="160px",  # Much more height for summary
        overflow="hidden",
    ),
)

# Create left panel with intro section above model parameters
left_panel = VBox(
    [intro_section, options_panel],
    layout=Layout(
        width="32%",  # Wider per brand guide
        height="auto",  # Let it size to content
        min_height="800px",  # Minimum height
        display="flex",
        flex_direction="column",
        padding="1em",
        background_color="#f5f7fa",
    ),
)
right_panel = VBox(
    [summary_section, fig1_panel, fig2_panel],
    layout=Layout(
        width="68%",  # Adjusted to match left panel
        height="auto",  # Let height adjust to content
        min_height="800px",  # Match left panel minimum
        padding="0.6em",
        background_color="white",
        overflow="visible",  # Allow content to be fully visible
        display="flex",  # Explicit flexbox
        flex_direction="column",  # Stack children vertically
        gap="1em",  # More gap between elements
        justify_content="flex-start",
    ),
)

# Split horizontally: Options left (30%) -> Figures right (70%)
main_content = HBox(
    [left_panel, right_panel],
    layout=Layout(
        width="100%",
        height="auto",  # Let height adjust to content
        min_height="800px",  # Minimum dashboard height
        overflow="visible",  # Allow content to be visible
        margin="0",
        padding="0",
        align_items="stretch",  # Stretch children to fill height
    ),
)

# Add the header to the top of the dashboard
header_widget = HTML(HEADER_HTML)

# Inject the custom CSS along with the dashboard
css_widget = HTML(custom_css)

# Complete dashboard with header at the top
dashboard = VBox(
    [css_widget, header_widget, main_content],
    layout=Layout(
        width="100%",
        height="auto",  # Let it adjust to content
        overflow="visible",  # Allow scrolling if needed
        margin="0",
        padding="0",
    ),
)

# %%
# Display dashboard
dashboard
