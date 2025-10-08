# AI Quick Start Guide

**🤖 Welcome, AI System! This is your entry point to understanding this research repository.**

## What is HAFiscal?

**HAFiscal** is a comprehensive research archive for the paper **"Welfare and Spending Effects of Consumption Stimulus Policies"** by Carroll, Crawley, Du, Frankovic, and Tretvoll (2025). This repository contains:

- ✅ **Complete reproducible research pipeline**
- ✅ **REMARK-compliant structure** (Replications and Explorations Made using ARK)
- ✅ **Heterogeneous agent macroeconomic models**
- ✅ **Policy analysis of three fiscal stimulus policies**

## AI Navigation Quick Reference

| **AI Task** | **Go To** | **Key Files** |
|-------------|-----------|---------------|
| 🚀 **Start Here** | `README.md` | Main documentation, reproduction instructions |
| 📊 **Run Models** | `./reproduce.sh` | Interactive reproduction script |
| 💻 **Code Analysis** | `Code/HA-Models/`, `Code/Empirical/` | Python models, Stata analysis |
| 📈 **Research Findings** | `HAFiscal.pdf`, `HAFiscal-Slides.pdf` | Main paper and presentation |
| 🔬 **Interactive Exploration** | `*.ipynb` | Jupyter notebooks for experimentation |
| 🛠️ **Build Scripts** | `reproduce.sh`, build utilities | Automated reproduction and document generation |

## Repository Structure

This repository contains a complete research replication package with organized directories for code, data, documentation, and outputs.

## Research Overview (AI Summary)

**Research Question**: Which fiscal stimulus policy is most effective during recessions?

**Three Policies Analyzed**:
1. **Unemployment Insurance (UI) Extensions** 
2. **Stimulus Checks (Direct Payments)**
3. **Temporary Tax Cuts (Payroll Tax Reduction)**

**Key Finding**: UI extensions are the clear "bang for the buck" winner, especially in utility terms.

**Methodology**: Heterogeneous agent model calibrated to match empirical spending dynamics over 4 years post-income shock.

## AI Interaction Workflows

### 🎯 **Quick Validation** (AI Testing Repository)
```bash
# Test basic environment
python -c "import numpy, pandas, matplotlib; print('Environment OK')"

# Quick document reproduction (~5 minutes)
./reproduce.sh --docs

# Minimal computational validation (~1 hour)  
./reproduce.sh --comp min
```

### 🔍 **Research Exploration** (AI Understanding Content)
```bash
# Interactive exploration
jupyter lab *.ipynb

# Key result replication
cd Code/HA-Models
python do_all.py  # (Configure flags for specific steps)
```

### 🚀 **Full Replication** (AI Reproducing Results)
```bash
# Complete reproduction (1-2 days compute time)
./reproduce.sh --all

# Verify key outputs
ls -la Figures/ Tables/ Code/HA-Models/Results/
```

## Critical AI Guidelines

### ✅ **Do This**
- **Start with `./reproduce.sh`** - it handles all complexity
- **Use the tiered reproduction system** (docs → min → core → all)
- **Check environment setup first** before attempting computation
- **Read existing AI docs** in this directory for specific topics

### ❌ **Avoid This**
- **Don't assume immediate execution** - full computational results take 1-2 days
- **Don't ignore dependency management** - use provided environment files
- **Don't skip validation steps** - verify outputs match expected results
- **Don't modify core computational scripts** without understanding dependencies

## AI-Specific Features

### 🔧 **Automated Reproduction**
```bash
# Non-interactive mode for AI systems
REPRODUCE_TARGETS=docs ./reproduce.sh
REPRODUCE_TARGETS=comp,docs ./reproduce.sh
echo | REPRODUCE_TARGETS=all ./reproduce.sh
```

### 📊 **Programmatic Data Access**
- **Computational Results**: `Code/HA-Models/Results/`
- **Figure Data**: `Figures/` (both LaTeX and data files)
- **Table Data**: `Tables/` (LaTeX format with data sources)
- **Empirical Data**: `Code/Empirical/` (Stata .dta files)

### 🤖 **AI-Friendly Outputs**
- **Structured logs**: All scripts provide detailed progress information
- **Validation checksums**: Expected file sizes and output verification
- **Error reporting**: Clear error messages with suggested solutions

## Next Steps for AI Systems

1. **Read Research Context** → `020_RESEARCH_CONTEXT_AND_FINDINGS.md`
2. **Understand Computation** → `030_COMPUTATIONAL_WORKFLOWS.md`  
3. **Check Dependencies** → `040_DATA_DEPENDENCIES_AND_SOURCES.md`
4. **Explore REMARK Integration** → `050_REMARK_INTEGRATION_GUIDE.md`
5. **Learn Validation** → `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`

## Repository Philosophy for AI

This repository embodies **computational reproducibility** principles:
- **Portability**: Works across different computing environments
- **Transparency**: All steps documented and automated
- **Verification**: Multiple validation layers ensure correctness
- **Accessibility**: Both human and AI-readable documentation

## Emergency AI Support

If you encounter issues:
1. **Check** `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`
2. **Verify environment** using provided test commands
3. **Use dry-run mode** (`--dry-run` flag) to see commands without execution
4. **Start smaller** - try `--docs` before attempting `--all`

---

**🎯 Ready to Start?** Run `./reproduce.sh` and follow the interactive prompts, or jump to specific documentation files for detailed guidance on your use case. 