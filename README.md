# HAFiscal Replication Package

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17861977.svg)](https://doi.org/10.5281/zenodo.17861977)
[![Docker Image](https://img.shields.io/badge/Docker-llorracc%2Fhafiscal--public-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/llorracc/hafiscal-public)
[![Powered by Econ-ARK](./@resources/econ-ark/PoweredByEconARK.svg)](https://econ-ark.org)
[![License](https://img.shields.io/badge/License-See%20LICENSE%20file-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9-blue.svg)](README/INSTALLATION.md)
[![Launch Dashboard](https://img.shields.io/badge/Launch-Interactive%20Dashboard-orange?logo=jupyter)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb)

**Paper**: *Welfare and Spending Effects of Consumption Stimulus Policies*  
**Authors**: Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, Håkon Tretvoll  
**Keywords**: heterogeneous agents, fiscal policy, stimulus checks, iMPCs, HANK, consumption, welfare, QE replication
**Version**: Development Version (HAFiscal-Latest)

---

## Instant Results (No Installation Required)

**Want to explore fiscal policy effects right now?**

[![Launch Interactive Dashboard](https://img.shields.io/badge/Launch-Interactive%20Dashboard-orange?style=for-the-badge&logo=jupyter)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb)

The **interactive dashboard** lets you:

- Compare stimulus checks, UI extensions, and tax cuts
- Adjust model parameters in real-time
- Visualize fiscal multipliers under different monetary policies
- See results in seconds (no 100+ hour computation needed)

**No installation required** — runs entirely in your browser via MyBinder.

For local installation, see [dashboard/DASHBOARD_README.md](dashboard/DASHBOARD_README.md) or [README/DASHBOARD.md](README/DASHBOARD.md).

---

## Quick Start

**New to HAFiscal?** Start with the [Getting Started Guide](README/GETTING-STARTED.md) for navigation and workflow guidance.

For detailed documentation, see the [README/](README/) directory.

The README/ directory contains:

- **[GETTING-STARTED.md](README/GETTING-STARTED.md)** — Navigation guide and workflow overview (start here if new)
- **Detailed README** — Complete replication instructions and documentation
- [INSTALLATION.md](README/INSTALLATION.md) — Installation and setup instructions
- [DOCKER.md](README/DOCKER.md) — Docker container usage and setup
- [DASHBOARD.md](README/DASHBOARD.md) — Interactive dashboard documentation
- [REPLICATION.md](README/REPLICATION.md) — Detailed replication instructions and data provenance
- [QUICK-REFERENCE.md](README/QUICK-REFERENCE.md) — Quick reference guide
- [CONTRIBUTING.md](README/CONTRIBUTING.md) — Contribution guidelines
- [TROUBLESHOOTING.md](README/TROUBLESHOOTING.md) — Common issues and solutions

---

## Research Questions and Contributions

### Primary Research Questions

1. **What are the welfare and spending effects of different consumption stimulus policies** (stimulus checks, tax cuts, unemployment insurance extensions) across the income and wealth distribution?

2. **How do heterogeneous-agent mechanisms** (liquidity constraints, sticky expectations, splurge behavior) affect the distributional and aggregate impacts of fiscal stimulus?

3. **What is the optimal design of stimulus policies** when accounting for household heterogeneity in marginal propensities to consume (MPCs)?

### Key Contributions

1. **Comprehensive HANK model calibration**: Extends heterogeneous-agent New Keynesian (HANK) models to match both microeconomic evidence on intertemporal MPCs (iMPCs) and macroeconomic evidence on aggregate consumption dynamics, using Survey of Consumer Finances (SCF) 2004 data.

2. **Novel behavioral mechanisms**: Implements and quantifies the role of:
   - **Sticky expectations** (following Carroll et al. 2020, `cAndCwithStickyE` in bibliography)
   - **Splurge behavior** (lumpy consumption responses to windfalls)
   - **Liquidity constraints** and heterogeneous wealth distributions

3. **Distributional welfare analysis**: Provides systematic welfare comparisons across alternative stimulus designs, highlighting how policy effectiveness varies dramatically across households with different liquid wealth positions.

4. **Methodological extension**: Builds on the computational framework of Auclert et al. (2021, `Auclert2021`) and extends the two-asset HANK literature (Kaplan & Violante 2014, `kaplan2014model`; Fagereng et al. 2021, `fagereng-mpc-2021`) to incorporate additional behavioral frictions.

---

## Literature Connections

### Core Methodological Foundations

**HANK Models and Computational Methods**:

- **Auclert et al. (2021)** [`Auclert2021`]: Sequence-space Jacobian methods for solving heterogeneous-agent models (computational framework extended here)
- **Kaplan & Violante (2014)** [`kaplan2014model`]: Two-asset model with liquid/illiquid assets and high MPCs for hand-to-mouth households (calibration strategy extended)
- **Carroll et al. (2017)** [`cstwMPC`]: Distribution of wealth and MPCs in heterogeneous-agent models (empirical targets extended)

**Sticky Expectations and Consumption Dynamics**:

- **Carroll et al. (2020)** [`cAndCwithStickyE`]: Sticky expectations model explaining aggregate consumption persistence (mechanism implemented here)
- **Lian (2023)** [`Lian2023-ca`]: Future consumption mistakes and high MPCs (related behavioral mechanism)

### Empirical Evidence on MPCs and Consumption Responses

**Microeconomic MPC Estimates**:

- **Fagereng et al. (2021)** [`fagereng-mpc-2021`]: Norwegian lottery data showing MPC heterogeneity by liquid assets (empirical target)
- **Kotsogiannis & Sakellaris (2024)** [`kotsogiannisMPCs`]: Tax lottery estimates of iMPCs (complementary evidence)
- **Boehm et al. (2025)** [`boehm2025fivefacts`]: Randomized experiment on MPCs (recent empirical evidence)
- **Parker et al. (2013)** [`parker2013consumer`]: Economic stimulus payments of 2008 (empirical benchmark)

**Consumption During Unemployment**:

- **Ganong & Noel (2019)** [`ganongConsumer2019`]: Consumer spending during unemployment (UI extension analysis relates)
- **Graves (2024)** [`gravesUnemployment`]: Unemployment risk and consumption dynamics (related mechanism)

### Fiscal Multipliers and Policy Analysis

**Fiscal Multipliers in HANK Models**:

- **Broer et al. (2023)** [`broer2023fiscalmultipliers`]: Fiscal multipliers from heterogeneous-agent perspective (complementary analysis)
- **Broer et al. (2025)** [`broer2025stimulus`]: Stimulus effects of common fiscal policies (recent related work)
- **Hagedorn et al. (2019)** [`hagedorn2019fiscal`]: Fiscal multiplier in HANK models (methodological connection)

**Automatic Stabilizers and Welfare**:

- **McKay & Reis (2016, 2021)** [`mckay2016role`, `mckay2021optimal`]: Role of automatic stabilizers and optimal design (welfare analysis relates)
- **Phan (2024)** [`phan2024welfare`]: Welfare consequences of countercyclical fiscal transfers (related welfare analysis)

### Behavioral Mechanisms

**Near-Rationality and Bounded Rationality**:

- **Andre et al. (2025)** [`ansQuickfix`]: Near-rationality in consumption and savings (related behavioral mechanism)
- **Akerlof & Yellen (1985)** [`akerlof1985near`]: Near-rational model of business cycle (foundational work)
- **Ilut & Valchev (2022)** [`ilutEconomic`]: Economic agents as imperfect problem solvers (related framework)

**Present Bias and Mental Accounting**:

- **Laibson et al. (2024)** [`lmmPresentBias`]: Present bias amplifies balance-sheet channels (related mechanism)
- **Graham & McDowall (2024)** [`graham2024mental`]: Mental accounts and consumption sensitivity (related behavioral feature)

### Related HANK Literature

**Unemployment and Business Cycles**:

- **Ravn & Sterk (2017, 2021)** [`Ravn2017`, `Ravn2021`]: Job uncertainty, HANK & SAM models (related HANK extensions)
- **Christiano et al. (2016)** [`Christiano2016`]: Unemployment and business cycles (search-and-matching framework)
- **Graves (2024)** [`gravesUnemployment`]: Unemployment risk affects business cycle dynamics (related mechanism)

**Distributional Effects of Monetary Policy**:

- **Gornemann et al. (2021)** [`Gornemann2021`]: Distributional consequences of systematic monetary policy (related distributional analysis)

### Data and Calibration

**SCF Data and Wealth Distribution**:

- **SCF 2004** [`SCF2004`]: Survey of Consumer Finances 2004 (primary data source)
- **Kaplan et al. (2014)** [`kaplan2014model`]: Liquid wealth construction methodology (followed here)

**Income Process Calibration**:

- **Crawley et al. (2024)** [`crawley2024parsimonious`]: Parsimonious model of idiosyncratic income (income process specification)

---

## What This Repository Provides (AI- and search-friendly summary)

- **Replication code and data** for the HAFiscal paper, built on Econ-ARK tools, with a Heterogeneous Agent New Keynesian (HANK) model calibrated to U.S. micro data.

- **Consumption stimulus policy analysis**: effects of stimulus checks, tax cuts, and UI extensions on spending, iMPCs, and welfare across the income and wealth distribution.

- **Model artifacts**: code for sticky expectations, splurge behavior, and robustness appendices (HTML/PDF links in appendices).

- **Data**: SCF-based liquid wealth and income moments (paper uses 2013-dollar SCF vintage; scripts document 2022→2013 inflation adjustment using CPI-U-RS and the 1.1587 factor).

- **Outputs**: paper PDFs, slides, tables, and figures for direct reuse in scholarly work or derivative projects.

---

## 5. Getting Started

For complete setup and reproduction instructions, see [README/GETTING-STARTED.md](README/GETTING-STARTED.md).

**Quick Summary**:

- **Installation**: See [README/INSTALLATION.md](README/INSTALLATION.md) for detailed setup instructions
- **Docker**: See [README/DOCKER.md](README/DOCKER.md) for containerized setup (alternative to local installation)
- **Reproduction**: Run `./reproduce.sh --help` to see available modes
- **Timing Estimates**: See [reproduce/benchmarks/TIMING-ESTIMATES.md](reproduce/benchmarks/TIMING-ESTIMATES.md) for hardware-specific timing data
- **Troubleshooting**: See [README/TROUBLESHOOTING.md](README/TROUBLESHOOTING.md) for common issues

**Quick Commands**:

```bash
# View all reproduction options
./reproduce.sh --help

# Quick document generation (5-10 minutes)
./reproduce.sh --docs

# Minimal computational validation (~1 hour)
./reproduce.sh --comp min

# Full computational replication (4-5 days)
./reproduce.sh --comp full
```

For detailed documentation on each mode, see [README/GETTING-STARTED.md](README/GETTING-STARTED.md).

---

## 6. Data Availability

This research uses publicly available data from the Survey of Consumer Finances (SCF) 2004. All data can be downloaded automatically via provided scripts.

**Data Sources**:

- **SCF 2004**: Board of Governors of the Federal Reserve System
  - Summary Extract: `rscfp2004.dta`
  - Full Public Data Set: `p04i6.dta`
  - Download: `Code/Empirical/download_scf_data.sh`
  - URL: <https://www.federalreserve.gov/econres/scf_2004.htm>

- **Norwegian Population Data**: Fagereng, Holm, and Natvik (2021)
  - Summary statistics and moments (published in paper)
  - Individual-level data not publicly available

**Data Files Included**: Data files are included in `Code/Empirical/` for convenience. See [README/REPLICATION.md](README/REPLICATION.md) for detailed data provenance and processing information.

**Citation**: Data sources are cited in `HAFiscal-Add-Refs.bib` and in the paper text (see `Subfiles/Parameterization.tex`).

---

## 7. Computational Requirements

**Hardware**: Minimum 4 cores, 8GB RAM; Recommended 8+ cores, 16GB RAM  
**Software**: Python 3.9+, LaTeX (TeX Live 2021+), Unix-like environment (macOS/Linux/WSL2)  
**Package Manager**: uv (recommended) or conda  
**Alternative**: Docker container (see [README/DOCKER.md](README/DOCKER.md))

For detailed requirements, platform support, and dependency information, see [README/INSTALLATION.md](README/INSTALLATION.md).

---

## 8. Reproduction

The primary reproduction script is `./reproduce.sh`, which provides multiple modes:

- `--docs`: Document generation only (5-10 minutes)
- `--comp min`: Minimal computational validation (~1 hour)
- `--comp full`: Full computational replication (4-5 days)
- `--all`: Complete reproduction pipeline

**Timing Estimates**: See [reproduce/benchmarks/TIMING-ESTIMATES.md](reproduce/benchmarks/TIMING-ESTIMATES.md) for detailed timing information and hardware scaling data.

For detailed reproduction instructions, see [README/GETTING-STARTED.md](README/GETTING-STARTED.md).

---

## 9. Results Mapping

This repository generates 6 main figures and 8 main tables, plus additional appendix figures and tables. All figures and tables are defined as LaTeX subfiles that include generated content from computational Python scripts.

**For complete details** on figure/table provenance, including:
- Exact LaTeX subfile locations
- Source PDF/LTX files and their paths
- Python scripts that generate each figure/table
- Captions and figure/table numbers
- Appendix figures and tables

See: **[README/REPLICATION.md - Section 6: Results Mapping](README/REPLICATION.md#6-results-mapping)**

### Quick Summary

**Figures**: Generated by Python scripts in `Code/HA-Models/` and compiled as LaTeX subfiles in `Figures/` directory. Main figures include:
- Splurge factor estimation (Figure 1)
- Wealth distribution fit (Figure 2)
- Non-targeted moments validation (Figure 3)
- Policy effectiveness during recessions (Figure 4)
- HANK-SAM model IRFs and multipliers (Figure 5)
- PE vs HANK multiplier comparison (Figure 6)

**Tables**: Generated by Python scripts and pulled into LaTeX via `\fetchgeneratedtabular{}`. Main tables include:
- MPC by wealth quartile (Table 1)
- Model calibration parameters (Table 2)
- Recession parameters (Table 3)
- Estimated discount factors (Table 4)
- Non-targeted moments (Table 5)
- Policy multipliers (Table 6)
- Welfare effectiveness (Table 7)
- Welfare comparison with splurge (Table 8)

**Parameter Values**: Model parameters are defined in:
- `Code/HA-Models/FromPandemicCode/Parameters.py` - Main parameter definitions
- `Code/HA-Models/FromPandemicCode/EstimParameters.py` - Estimation parameters

**Note**: Each figure and table `.tex` file can be compiled standalone. See [README/REPLICATION.md](README/REPLICATION.md#6-results-mapping) for detailed compilation instructions and complete provenance information.

---

## 10. File Organization (simplified)

```
/
├── README.md							 # This file
├── environment.yml						 # Conda environment specification
├── pyproject.toml						 # Python dependencies (uv format)
├── HAFiscal.tex						 # Main LaTeX document
├── HAFiscal.bib						 # Bibliography
├── HAFiscal-Abstract.txt				 # Abstract text
├── HAFiscal-Slides.tex					 # Presentation slides
├── reproduce.sh						 # Main reproduction script
├── reproduce.py						 # Python mirror (cross-platform)
├── reproduce_min.sh					 # Quick validation test
├── reproduce/							 # Additional reproduction scripts
│   ├── reproduce_computed.sh			 # Run all computations
│   ├── reproduce_computed_min.sh		 # Minimal computation test
│   ├── reproduce_documents.sh			 # Generate LaTeX documents
│   ├── reproduce_environment_comp_uv.sh # Set up Python environment (uv)
│   ├── reproduce_environment_texlive.sh # Set up LaTeX environment
│   └── [other reproduction scripts]
├── Code/								 # All computational code
│   ├── HA-Models/						 # Heterogeneous agent models
│   │   ├── FromPandemicCode/			 # Core model implementation
│   │   ├── Results/					 # Model output files
│   │   └── [model-specific directories]
│   └── Empirical/						 # Empirical data processing
│       ├── download_scf_data.sh		 # Download SCF data
│       ├── make_liquid_wealth.py		 # Construct liquid wealth measure
│       ├── adjust_scf_inflation.py		 # Inflation adjustments
│       └── compare_scf_datasets.py		 # Dataset comparisons
├── Figures/							 # Figure LaTeX files (*.tex, *.pdf)
├── Tables/								 # Table LaTeX files (*.tex, *.pdf)
├── Subfiles/							 # Paper section files
│   ├── Appendix-*.tex					 # Appendix sections
│   ├── Conclusion.tex					 # Conclusion section
│   └── [other section files]
├── Data/								 # Data files directory
├── dashboard/							 # Interactive dashboard (Jupyter/Streamlit)
├── binder/								 # Binder configuration for cloud execution
├── Equations/							 # Equation definitions
├── @local/								 # Local LaTeX packages and configuration
└── @resources/							 # LaTeX resources and utilities
```

---

## 11. Known Issues and Workarounds

For detailed troubleshooting information, see [README/TROUBLESHOOTING.md](README/TROUBLESHOOTING.md).

**Common Issues**:

- **Windows Native**: Not supported; use WSL2 (see [README/INSTALLATION.md](README/INSTALLATION.md))
- **Long Computation Times**: Use `./reproduce.sh --comp min` for quick validation
- **LaTeX Issues**: See [README/TROUBLESHOOTING.md](README/TROUBLESHOOTING.md) for platform-specific solutions

<!-- No LaTeX font issues for Latest version (uses econark class) -->

---

## 12. Contact Information

### Technical Issues

For technical issues with replication:

- Open an issue: https://github.com/llorracc/HAFiscal-Latest/issues
- Email: <ccarroll@jhu.edu> (Christopher Carroll)

### Data Questions

For questions about SCF data:

- Federal Reserve SCF page: <https://www.federalreserve.gov/econres/scfindex.htm>
- Email: <scf@frb.gov>

### Paper Content

For questions about the paper content:

- See author emails in paper
- Christopher Carroll: <ccarroll@jhu.edu>
- Edmund Crawley: <edmund.s.crawley@frb.gov>

---

## 13. Citation

If you use this replication package, please cite:

```bibtex
@misc{carroll2025hafiscal,
  title={Welfare and Spending Effects of Consumption Stimulus Policies},
  author={Carroll, Christopher D. and Crawley, Edmund and Du, William and Frankovic, Ivan and Tretvoll, H{\aa}kon},
  year={2025},
  howpublished={Development version},
  note={Available at \url{https://github.com/llorracc/HAFiscal-Latest}}
}
```

---

**Last Updated**: January 11, 2026  
**README Version**: 1.1  
**Replication Package Version**: 1.0

**Version 1.1 Changes**:
- Added comprehensive `reproduce.sh` documentation with all modes
- Updated timing data to use benchmark system measurements (not placeholders)
- Added hardware scaling examples (minimum, mid-range, high-performance)
- Integrated benchmark system references and instructions
- Added timing variability factors and explanations

**Note**: This is the development version. For public release, see HAFiscal-Public. For journal submission, see HAFiscal-QE.
