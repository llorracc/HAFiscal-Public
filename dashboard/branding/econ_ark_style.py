"""
Econ-ARK branding and style definitions for use in Python applications.
Contains color schemes, plot styles, and HTML/CSS styling.
"""

from cycler import cycler

# Define Econ-ARK brand colors and styling
ARK_BLUE = "#005b8f"      # primary
ARK_LIGHTBLUE = "#0ea5e9" # lighter accent
ARK_ORANGE = "#f97316"    # accent
ARK_GREEN = "#047857"     # accent
ARK_SLATE_DK = "#1e293b"  # dark text
ARK_SLATE_LT = "#475569"  # light text
ARK_GREY = "#6b7280"      # utility
ARK_GRID = "#e2e8f0"      # grid lines
ARK_PANEL = "#f1f5f9"     # panel background

# Define refined Econ-ARK colors and styling
ARK_PANEL_LIGHT = "#f8fafc"  # Lighter panel background
ARK_GRID_SOFT = "#edf2f7"    # Softer grid lines
ARK_SPINE = "#94a3b8"        # Professional spine color
ARK_TEXT = "#334155"         # Clear, professional text color

# Matplotlib style configuration
MATPLOTLIB_STYLE = {
    # --- Font & text ---
    "font.family": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "600",  # Bolder titles
    "axes.labelsize": 9,  # Smaller axis labels
    "axes.labelweight": "500",  # Slightly bolder labels
    "xtick.labelsize": 8.5,  # Slightly smaller tick labels
    "ytick.labelsize": 8.5,
    # Text colors
    "text.color": ARK_TEXT,
    "axes.labelcolor": ARK_TEXT,
    "axes.titlecolor": ARK_BLUE,  # Brand color for all titles including subplots
    "xtick.color": ARK_TEXT,
    "ytick.color": ARK_TEXT,
    
    # --- Colours & lines ---
    "axes.prop_cycle": cycler(color=[ARK_BLUE, ARK_ORANGE, ARK_GREEN, ARK_LIGHTBLUE, ARK_SLATE_LT]),
    "axes.edgecolor": ARK_SPINE,
    "axes.linewidth": 1.2,  # Slightly thicker spines
    "grid.color": ARK_GRID_SOFT,
    "grid.linestyle": "-",
    "grid.linewidth": 0.6,
    "grid.alpha": 0.7,  # Subtle grid
    
    # --- Background & figure ---
    "axes.facecolor": ARK_PANEL_LIGHT,  # Very light blue-gray background
    "figure.facecolor": "white",
    "figure.dpi": 110,
    
    # --- Spines ---
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": True,
    "axes.spines.bottom": True,
    
    # --- Legend ---
    "legend.frameon": True,
    "legend.framealpha": 0.95,
    "legend.edgecolor": ARK_SPINE,
    "legend.fontsize": 9,
    "legend.title_fontsize": 10,
    
    # --- Lines & markers ---
    "lines.linewidth": 2.0,
    "lines.markersize": 6,
    "lines.markeredgewidth": 1.5,
    "lines.markeredgecolor": "white",  # White edge on markers
    
    # --- Ticks ---
    "xtick.major.width": 1.2,
    "ytick.major.width": 1.2,
    "xtick.minor.width": 0.6,
    "ytick.minor.width": 0.6,
}

# HTML/CSS styles for dashboard
DASHBOARD_CSS = """
<style>
    :root {
        /* Brand colors */
        --ark-blue: #005b8f;          /* primary */
        --ark-lightblue: #0ea5e9;     /* lighter accent */
        --ark-slate-dk: #1e293b;      /* dark text */
        --ark-slate-lt: #475569;      /* light text */
        --ark-grid: #e2e8f0;          /* grid lines */
        --ark-panel: #f1f5f9;         /* panel background */
        --ark-body: 0.95rem;          /* base text size */
    }

    /* ===== HEADING SCALE & DECORATION ===== */
    h1, .ark-h1 {
        font:700 1.65rem/1.3 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
        color:var(--ark-blue);
    }

    h2, .ark-h2 {
        font:600 1.35rem/1.35 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
        color:var(--ark-slate-dk);
        position:relative;
        margin-bottom:1.1rem;
    }
    h2::after, .ark-h2::after {              /* full-width underline bar */
        content:'';
        position:absolute;
        left:0; bottom:-6px;
        width:100%; height:2px;
        background:var(--ark-blue);
        opacity: 0.9;
    }

    /* Optional lighter accent for figures */
    .ark-h2.lightblue { color:var(--ark-lightblue); }
    .ark-h2.lightblue::after { 
        background:var(--ark-lightblue);
        opacity: 0.8;  /* Slightly more transparent for lightblue */
    }

    h3, .ark-h3 {
        font:600 1.15rem/1.4 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
        color:var(--ark-slate-dk);
    }

    /* Body and utility classes */
    p.ark-body {font-size:var(--ark-body);line-height:1.45;color:var(--ark-slate-dk);}
    .ark-num {color:var(--ark-blue);font-weight:600;}
    .ark-label {font-size:0.9rem;font-weight:500;color:var(--ark-slate-lt);}
    
    /* Parameter group boxes */
    .param-group {
        background-color: var(--ark-panel);
        padding: 1.25em;
        margin: 0.75em 0 1.75em 0;
        border-radius: 8px;
        border: 1px solid var(--ark-grid);
    }

    /* === HEADER LAYOUT ===================================== */
    .ark-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #005b8f;
        padding: 0px 0px;
        position: sticky;
        top: 0;
        z-index: 1000;
        box-shadow: 0 0px 0px rgba(0,0,0,0.15);
    }
    
    .ark-header img {
        height: 64px;
        margin-right: 20px;
    }
    
    .ark-header span {
        color: #fff;
        font: 600 1.35rem/1 system-ui, sans-serif;
        letter-spacing: -0.01em;
        flex: 1;
    }

    /* nav quick‑links on the right */
    .ark-nav {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-left: auto;
        margin-right: 40px;
        flex-shrink: 0;
    }
    
    .ark-nav__link {
        font-size: 0.85rem;
        color: #e5f1ff !important;
        text-decoration: none;
        transition: opacity 0.15s ease;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
    }
    
    .ark-nav__link:hover {
        opacity: 0.8;
    }
</style>
"""

# Favicon HTML for browser tab
FAVICON_HTML = """
<link rel="icon" type="image/x-icon" href="branding/favicon.ico">
<link rel="shortcut icon" type="image/x-icon" href="branding/favicon.ico">
"""

# Header HTML with Econ-ARK logo
HEADER_HTML = """
<div class='ark-header'>
  <a href='https://econ-ark.org' target='_blank' style='border:0'>
    <img src='https://econ-ark.org/assets/img/econ-ark-logo-white.png'
         alt='Econ‑ARK logo'>
  </a>
  <span>HANK‑SAM Interactive Dashboard</span>
  
  <!-- Navigation links on the right -->
  <nav class='ark-nav'>
    <a href='https://github.com/econ-ark/HAFiscal/blob/master/docs/HAFiscal.pdf' target='_blank' class='ark-nav__link'>Working paper ↗</a>
    <a href="http://45.55.225.169:8501/" target="_blank" class="ark-nav__link">Chat with Econ-ARK AI ↗</a>
    <a href='https://github.com/econ-ark/HAFiscal' target='_blank' class='ark-nav__link'>
      <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" style='width:16px; height:16px; fill:currentColor; margin-right:0.1em;'>
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
      </svg>
      GitHub repo ↗
    </a>
  </nav>
</div>
"""

def tidy_legend(fig):
    """Helper to format legends consistently across all figures."""
    # Remove any existing legends from subplots
    for ax in fig.axes:
        if ax.get_legend() is not None:
            ax.get_legend().remove()
    
    # Get all unique handles and labels from all subplots
    handles, labels = [], []
    for ax in fig.axes:
        h, l = ax.get_legend_handles_labels()
        for handle, label in zip(h, l):
            if label not in labels:  # Only add unique items
                handles.append(handle)
                labels.append(label)
    
    # Add single legend below the figure
    fig.legend(handles, labels,
              bbox_to_anchor=(0.5, -0.1),  # Position below figure
              loc='center',
              ncol=3,  # Horizontal 3-column layout
              prop={'size': 9},
              frameon=True,
              framealpha=0.95,
              edgecolor='#cbd5e1')
    
    # Adjust subplot spacing
    fig.subplots_adjust(bottom=0.25, wspace=0.2) 


DASH_STYLE = DASHBOARD_CSS + """<!-- Force refresh 1754384775 -->
<style>
    /* Define Econ-ARK pink and pill styling */
    :root {
        --ark-pink: #ec4899;
        --ark-blue: #005b8f;          /* dark brand blue  */
        --ark-blue-light: #c7e3f9;    /* 20 % tint of blue */
    }

    /* Econ-ARK pill box styling */
    .ark-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.4em;
        padding: 0.35em 0.85em;
        background: #f3f4f6;
        border: 1px solid #e5e7eb;
        border-radius: 20px;
        color: #005b8f;
        text-decoration: none;
        font-size: 0.95rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .ark-pill:hover {
        background: #e5e7eb;
        border-color: #d1d5db;
        color: #004a73;
        text-decoration: none;
    }
    
    .ark-pill svg {
        width: 14px;
        height: 14px;
        fill: currentColor;
    }

    /* Professional dashboard styling inspired by modern analytics platforms */
    
    /* Main header with pink styling */
    h1.ark-h1-pink {
        font: 700 1.25rem/1.3 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
        color: var(--ark-pink);
        position: relative;
        margin-bottom: 0.8rem;
    }

    .ark-h2 {
        font: 600 1.1rem/1.2 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
        margin-bottom: 0.5rem;
    }

    h1.ark-h1-pink::after {
        content: '';
        position: absolute;
        left: 0; 
        bottom: -6px;
        width: 100%; 
        height: 3px;
        background: var(--ark-pink);
        opacity: 0.9;
    }
    
    /* Green variant for h2 */
    .ark-h2.green { 
        color: #047857; 
    }
    .ark-h2.green::after { 
        background: #047857;
        opacity: 0.9;
    }
    
    /* Reduce bottom margin for plot headings */
    .plot-heading {
        margin-bottom: 0.3rem !important;
    }
    
    /* Section headings - consistent professional styling */
    .section-heading {
        font-weight: 600 !important;
        color: #1a202c !important;
        font-size: 0.875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
        margin-bottom: 0.3rem !important;
        padding-left: 0 !important;
        border: none !important;
    }
    
    /* Widget containers with subtle depth */
    .parameter-card {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 0.4rem !important;
        margin-bottom: 0.5rem !important;
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
    
    /* Enhanced slider styling - professional look - FIX CLIPPING */
    .widget-slider {
        margin: 1.2em 0 !important;
        overflow: visible !important;  /* Allow handle to show */
    }
    
    .widget-label {
        font-weight: 500 !important;
        color: #2d3748 !important;
        font-size: 0.875rem !important;
        margin-bottom: 0.5em !important;
    }
    
    /* Technical looking readout - smaller, black text */
    .widget-readout {
        background: #ffffff !important;
        color: #000000 !important;
        padding: 0.15em 0.5em !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        min-width: 3em !important;
        text-align: center !important;
        border: 1px solid #e2e8f0 !important;
        font-family: system-ui, -apple-system, sans-serif !important;
    }
    
    /* Modern slider track */
    .ui-slider {
        background: #e2e8f0 !important;
        height: 4px !important;
        border-radius: 2px !important;
        position: relative !important;
        margin: 0 12px !important;  /* Add margin to prevent clipping */
        overflow: visible !important;
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
        margin-left: -10px !important;
    }
    
    .ui-slider-handle:hover {
        transform: scale(1.1) !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.15) !important;
    }
    
    .ui-slider-handle:active {
        transform: scale(0.95) !important;
    }
    
    /* Clean inline slider styling */
    .slider-container-inline {
        margin: 0 0 0.25rem 0 !important;
        padding: 0 !important;
    }
    
    .inline-slider-label {
        font-weight: 500 !important;
        color: #2d3748 !important;
        font-size: 0.775rem !important;
        margin: 0 0 0.2rem 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: baseline !important;
    }
    
    .inline-slider-value {
        font-weight: 600 !important;
        color: #000000 !important;
        font-size: 0.75rem !important;
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 4px !important;
        padding: 0.15em 0.5em !important;
        margin-left: 0.5rem !important;
        min-width: 2.5em !important;
        text-align: center !important;
        font-family: system-ui, -apple-system, sans-serif !important;
    }
    
    .slider-container-inline .widget-slider {
        margin: 0.5rem 0.75rem !important;  /* Space for handle */
        padding: 0 !important;
        overflow: visible !important;  /* Ensure handle not clipped */
    }
    
    /* Ensure slider track has space */
    .slider-container-inline .ui-slider {
        overflow: visible !important;
        margin: 0 !important;  /* Track itself has no extra margin */
    }
    
    /* Ensure handle is fully visible */
    .slider-container-inline .ui-slider-handle {
        z-index: 10 !important;  /* Above other elements */
    }

    /* Professional button styling - Econ-ARK orange */
    .widget-button {
        background: #f97316 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75em 1.5em !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.025em !important;
        box-shadow: 0 2px 4px rgba(249, 115, 22, 0.2) !important;
        transition: all 0.2s ease !important;
        text-align: center !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    .widget-button:hover:not(:disabled) {
        background: #ea580c !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(249, 115, 22, 0.3) !important;
    }
    
    .widget-button:active:not(:disabled) {
        transform: translateY(0) !important;
    }
    
    .widget-button:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }
    
    /* ─── Override the generic orange button just for preset pills - REMOVE SHADOWS ────────────── */
    .widget-button.preset-btn {
        background: var(--ark-blue-light) !important;
        border-color: var(--ark-blue-light) !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        font-size: 9px !important;  /* Even smaller for better fit */
        font-weight: 500 !important;
        padding: 3px 6px !important;  /* Tighter padding */
        margin-right: 2px !important;
        cursor: pointer !important;
        transition: all .15s ease !important;
        text-transform: none !important;
        letter-spacing: normal !important;
        box-shadow: none !important;  /* REMOVE ALL SHADOWS */
    }

    .widget-button.preset-btn.active {
        background: var(--ark-blue) !important;
        border-color: var(--ark-blue) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }

    .widget-button.preset-btn:hover {
        background: var(--ark-blue) !important;
        border-color: var(--ark-blue) !important;
        color: #ffffff !important;
        box-shadow: none !important;
        transform: none !important;
    }
    /* Larger preset buttons for longer text */
    .widget-button.preset-btn-large {
        background: var(--ark-blue-light) !important;
        border-color: var(--ark-blue-light) !important;
        color: #ffffff !important;
        border-radius: 15px !important;
        font-size: 11px !important;  /* 1 point larger than regular (13px) */
        font-weight: 500 !important;
        padding: 7px 12px !important;
        margin: 0 4px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        text-transform: none !important;
        letter-spacing: 0.01em !important;
        box-shadow: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        line-height: 1.3 !important;
    }

    .widget-button.preset-btn-large.active {
        background: var(--ark-blue) !important;
        border-color: var(--ark-blue) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }

    .widget-button.preset-btn-large:hover {
        background: var(--ark-blue) !important;
        border-color: var(--ark-blue) !important;
        color: #ffffff !important;
        box-shadow: none !important;
        transform: none !important;
    }
    
    /* Status indicator styling */
    .status-container {
        background: #f7fafc !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        padding: 0.5em 0.75em !important;
        margin-top: 0.5em !important;
    }
    
    /* Clean sidebar styling */
    .sidebar-container {
        overflow: visible !important;  /* Prevent clipping */
    }
    
    /* Remove grey underline from main subtitle only */
    .main-subtitle {
        border-bottom: none !important;
    }
    .main-subtitle::after {
        display: none !important;
    }
    
    /* Scenario tab styling with reduced padding and smaller font - CONDENSE MORE */
    .widget-tab .p-TabBar-tabLabel {
        padding: 0.2rem 0.3rem !important;  /* Even smaller padding */
        font-size: 0.9rem !important;  /* Smaller font */
    }
    
    .widget-tab > .p-TabBar {
        margin-bottom: 0.2rem !important;  /* Reduce bottom margin */
    }
    
    .widget-tab .p-TabPanel {
        padding: 0 !important;
    }
    
    /* Match dashboard readout style for value boxes */
    .slider-container-inline .widget-label-value {
        background: #ffffff !important;
        color: #000000 !important;
        padding: 0.15em 0.5em !important;
        border-radius: 4px !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        text-align: center !important;
        border: 1px solid #e2e8f0 !important;
        font-family: system-ui, -apple-system, sans-serif !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-height: 22px !important;
        line-height: 1.2 !important;
    }

    
    /* Link styling */
    .resource-link {
        display: inline-flex;
        align-items: center;
        gap: 0.4em;
        color: #005b8f;
        text-decoration: none;
        transition: all 0.2s ease;
        padding: 0.2em 0;
    }
    
    .resource-link:hover {
        color: #004a73;
        text-decoration: underline;
    }
    
    .resource-link svg {
        width: 16px;
        height: 16px;
        fill: currentColor;
    }
    
    /* Improved key insights bullets */
    .key-insights-list {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    
    .key-insights-list li {
        position: relative;
        padding-left: 1.75rem;
        margin-bottom: 0;
        line-height: 1.6;
        color: #2d3748;
        font-size: 1rem;
    }
    
    .key-insights-list li:before {
        content: '';
        position: absolute;
        left: 0;
        top: 0.6em;
        width: 6px;
        height: 6px;
        background: var(--ark-blue);
        border-radius: 50%;
    }
    
    .key-insights-list li:last-child {
        margin-bottom: 0;
    }
    
    /* Remove all top margin/padding */
    body {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .jp-Notebook {
        padding-top: 0 !important;
    }
    
    .jp-Cell {
        margin-top: 0 !important;
    }
    
    .jp-Cell:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    /* Ensure header is at very top */
    .ark-header {
        display: flex !important;
        align-items: center !important;
        background: #005b8f !important;
        padding: 20px 20px 16px 20px !important;  /* More top padding for logo */
        margin: 0 !important;  /* No negative margin needed */
        position: relative !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        z-index: 1000 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
    }
    
    .ark-header img {
        height: 40px !important;  /* Sized to fit with padding */
        margin-right: 18px !important;
        display: block !important;  /* Ensure proper rendering */
    }
    
    .ark-header span {
        color: #fff !important;
        font: 600 1.3rem/1 system-ui,sans-serif !important;  /* Slightly smaller font */
        letter-spacing: -0.01em !important;
    }

    /* ===== DASHBOARD POLISH FIXES ===== */
    
    /* KILL ALL BUTTON SHADOWS */
    .widget-button.preset-btn,
    .widget-button.preset-btn:hover,
    .widget-button.preset-btn:focus,
    .widget-button.preset-btn:active,
    .widget-button.preset-btn.active {
        box-shadow: none !important;
        transform: none !important;
    }
    
    /* FIX BUTTON CLIPPING */
    .widget-button.preset-btn {
        line-height: 1 !important;
        padding-top: 5px !important;
        overflow: visible !important;
    }
    
    /* Fix container overflow */
    .preset-buttons-container {
        overflow: visible !important;
        padding-top: 2px !important;
    }

    /* Force preset button styling - high specificity */
    .widget-area .widget-button.preset-btn,
    .widget-container .widget-button.preset-btn {
        font-size: 11px !important;
        padding: 8px 14px !important;
        margin: 0 5px !important;
        letter-spacing: 0.02em !important;
        line-height: 1.4 !important;
    }
    
    /* Ensure container spacing */
    .widget-container .widget-hbox {
        margin: 1rem 0 1.5rem 0 !important;
    }
</style>
"""