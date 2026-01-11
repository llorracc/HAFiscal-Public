# HAFiscal Repository Summary
*Generated on 2025-07-20 at 14:22*

## Overview

The **HAFiscal** repository contains the complete software archive for the paper "Welfare and Spending Effects of Consumption Stimulus Policies" by Carroll, Crawley, Du, Frankovic, and Tretvoll (2025), forthcoming in *Quantitative Economics*.

## Research Purpose

This research evaluates the effectiveness of three fiscal stimulus policies commonly used during recessions:
1. **Unemployment Insurance (UI) extensions**
2. **Stimulus checks** (means-tested transfers)
3. **Payroll tax cuts** (temporary wage tax reductions)

The study uses a heterogeneous agent (HA) model calibrated to match empirical spending dynamics following income shocks, specifically the intertemporal marginal propensity to consume (iMPC) patterns documented by Fagereng, Holm, and Natvik (2021).

## Key Findings

- **UI extensions** provide the highest "bang for the buck" in utility terms
- **Stimulus checks** are second-best and offer advantages of speed and scalability
- **Payroll tax cuts** are considerably less effective, especially without multipliers
- The model incorporates "splurge behavior" to capture excess initial spending observed in data
- Results are evaluated using both spending and welfare metrics

## Repository Structure

### Core Research Files
- `HAFiscal.tex` - Main LaTeX document
- `HAFiscal.txt` - Full paper text (3,343 lines)
- `HAFiscal-Slides.tex` - Presentation slides
- `HAFiscal-dashboard.ipynb` - Interactive Jupyter dashboard
- `HAFiscal-jupyterlab.ipynb` - Alternative Jupyter notebook

### Computational Code (`Code/`)
- **`Code/HA-Models/`** - Main computational framework
  - `do_all.py` - Master script orchestrating 5-step workflow
  - `Target_AggMPCX_LiquWealth/` - Estimation of splurge factor (Step 1)
  - `FromPandemicCode/` - Core model implementation (Steps 2-5)
  - `Results/` - Output files and tables
  - `StickyExpectations/` - Additional model variants
  - `Results_HANK/` - HANK model results

- **`Code/Empirical/`** - Data processing and empirical analysis
  - `make_liquid_wealth.do` - Stata script for wealth analysis
  - `rscfp2004.dta/csv` - Survey of Consumer Finances 2004 data
  - `ccbal_answer.dta/csv` - Credit card balance data

### Reproduction Scripts
- `reproduce.sh` - Main reproduction script
- `reproduce_min.sh` - Minimal reproduction (<1 hour)
- `reproduce_document_pdf.sh` - PDF generation
- `reproduce_document_pdf_all.sh` - Complete document build

### Documentation
- `README.md` - Comprehensive project documentation
- `CITATION.cff` - Citation metadata
- `LICENSE` - MIT license
- `binder/environment.yml` - Conda environment specification

## Computational Workflow

The research follows a 5-step computational process:

1. **Step 1** (~20 min): Estimate splurge factor and create Figure 1
2. **Step 2** (~21 hours): Estimate discount factor distributions, create Figure 2
3. **Step 3** (optional): Robustness analysis with splurge=0
4. **Step 4** (~1 hour): Solve HANK and SAM models, create Figure 5
5. **Step 5** (~65 hours): Compare fiscal policies, create Figures 4,6 and Tables 4-8

## Technical Requirements

### Software Dependencies
- **Python 3.11.7** with conda-forge channel
- **Stata** (MP/18.0 or compatible)
- **LaTeX** (for document generation)
- Key Python packages: econ-ark, numpy, matplotlib, scipy, pandas, numba, sequence-jacobian

### Hardware Requirements
- Modern laptop (2025) with sufficient RAM
- Full reproduction takes several days
- Minimal version (<1 hour) available for quick testing

## Data Sources

- **Survey of Consumer Finances 2004** (Federal Reserve Board)
- **Norwegian registry data** (for iMPC calibration)
- All data publicly available with proper attribution

## Key Model Features

### Heterogeneous Agent Framework
- Calibrated to match liquid wealth distribution
- Incorporates education heterogeneity
- Matches empirical iMPC patterns over 4 years

### "Splurge" Behavior
- Captures excess initial spending on income shocks
- High MPC portion of income across all wealth levels
- Consistent with empirical evidence

### Policy Analysis Framework
- Partial equilibrium with optional multiplier effects
- HANK-SAM general equilibrium robustness check
- Welfare and spending effectiveness metrics

## Outputs Generated

### Tables (4-8)
- Policy comparison results
- Wealth and MPC statistics
- Welfare analysis
- Multiplier effects

### Figures (1-6)
- iMPC patterns and model fit
- Discount factor distributions
- Policy impulse responses
- Welfare comparisons

### Interactive Components
- Jupyter dashboard for policy exploration
- Reproducible computational pipeline
- Comprehensive documentation

## Research Contributions

1. **Methodological**: Novel integration of microeconomic heterogeneity with fiscal policy analysis
2. **Empirical**: Calibration to high-quality spending dynamics data
3. **Policy**: Clear ranking of stimulus policy effectiveness
4. **Technical**: Reproducible computational framework for policy analysis

## Replication Status

- **Fully reproducible** with provided scripts
- **Deterministic** optimization routines
- **Comprehensive documentation** of all steps
- **Public data** with clear provenance
- **Open source** code under MIT license

## Contact Information

- **Christopher D. Carroll**: Johns Hopkins University, NBER
- **Edmund Crawley**: Federal Reserve Board
- **William Du**: Johns Hopkins University
- **Ivan Frankovic**: Deutsche Bundesbank
- **Håkon Tretvoll**: Statistics Norway, BI Norwegian Business School

---

*This summary was generated by examining the repository structure, documentation, and key files to provide a comprehensive overview of the HAFiscal research project.* 