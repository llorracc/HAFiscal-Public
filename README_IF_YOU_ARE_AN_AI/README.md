# README_IF_YOU_ARE_AN_AI Directory - Documentation Index

**🤖 Welcome to the AI Documentation Center**

This directory contains comprehensive documentation specifically designed for AI systems to understand, navigate, and interact with this research repository.

## 📋 **Documentation Index**

### 🚀 **Start Here** (Essential for All AI Systems)

| File | Purpose | Priority |
|------|---------|----------|
| [`000_AI_QUICK_START_GUIDE.md`](000_AI_QUICK_START_GUIDE.md) | **Main entry point** - Navigation, workflows, key concepts | **🔴 CRITICAL** |
| [`010_PAPER_ABSTRACT_AND_CLAIMS.md`](010_PAPER_ABSTRACT_AND_CLAIMS.md) | **Paper abstract, key claims, quantitative results** | **🔴 CRITICAL** |
| [`020_RESEARCH_CONTEXT_AND_FINDINGS.md`](020_RESEARCH_CONTEXT_AND_FINDINGS.md) | Research overview, methodology, key findings | **🔴 CRITICAL** |
| [`080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`](080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md) | Common issues, debugging, validation strategies | **🔴 CRITICAL** |
| [`SUMMARY.json`](SUMMARY.json) | **Machine-readable key facts** (JSON format) | **🔴 CRITICAL** |

### 🔧 **Technical Implementation** (For AI Doing Computation/Analysis)

| File | Purpose | Priority |
|------|---------|----------|
| [`030_COMPUTATIONAL_WORKFLOWS.md`](030_COMPUTATIONAL_WORKFLOWS.md) | Detailed 5-step computational pipeline with runtime estimates | **🟡 HIGH** |
| [`035_MODEL_SUMMARY.md`](035_MODEL_SUMMARY.md) | **Mathematical model equations, calibration, solution methods** | **🟡 HIGH** |
| [`040_MATHEMATICAL_STRUCTURE.md`](040_MATHEMATICAL_STRUCTURE.md) | **Comprehensive mathematical framework, equation hierarchy, computational structure** | **🟡 HIGH** |
| [`045_EQUATION_MAP.md`](045_EQUATION_MAP.md) | **Equation-to-code mapping, paper references, parameter values** | **🟡 HIGH** |
| [`047_STATE_SPACE_AND_FLOW.md`](047_STATE_SPACE_AND_FLOW.md) | **State space structure, state transitions, computational flow diagrams** | **🟡 HIGH** |
| [`048_RAG_INDEXING_STRATEGY.md`](048_RAG_INDEXING_STRATEGY.md) | **RAG indexing recommendations for mathematical content, chunking strategies, metadata extraction** | **🟢 MEDIUM** |
| [`040_DATA_DEPENDENCIES_AND_SOURCES.md`](040_DATA_DEPENDENCIES_AND_SOURCES.md) | Data sources, formats, integration requirements | **🟡 HIGH** |
| [`060_CODE_NAVIGATION.md`](060_CODE_NAVIGATION.md) | **Code directory structure, key files, entry points** | **🟡 HIGH** |
| [`070_INTERACTIVE_DASHBOARD.md`](070_INTERACTIVE_DASHBOARD.md) | **Interactive HANK-SAM dashboard usage** | **🟡 HIGH** |
| [`050_REMARK_INTEGRATION_GUIDE.md`](050_REMARK_INTEGRATION_GUIDE.md) | REMARK ecosystem integration, standards compliance | **🟡 HIGH** |

### 📚 **Specialized Documentation** (For Specific Topics)

| File | Purpose | Priority |
|------|---------|----------|
| [`SUBFILE_CROSS_REFERENCE_ARCHITECTURE.md`](SUBFILE_CROSS_REFERENCE_ARCHITECTURE.md) | **⚠️ CRITICAL**: `\whenintegrated{}` system, cross-references between subfiles | **🔴 CRITICAL** |
| [`BUILD_SYSTEM_VERBOSITY.md`](BUILD_SYSTEM_VERBOSITY.md) | Output verbosity controls (PDFLATEX_QUIET, VERBOSITY_LEVEL) | **🟡 HIGH** |
| [`EXPECTED_WARNINGS.md`](EXPECTED_WARNINGS.md) | Expected LaTeX warnings, intentional hyperref warnings | **🟡 HIGH** |
| [`CURSOR_INDEXING_STRATEGY.md`](CURSOR_INDEXING_STRATEGY.md) | Cursor AI indexing optimization (1.75GB excluded, what's indexed) | **🟡 HIGH** |
| [`CURSOR_SST_THREE_FILE_ARCHITECTURE.md`](CURSOR_SST_THREE_FILE_ARCHITECTURE.md) | SST pattern: .gitignore + .additions → .cursorindexingignore | **🟡 HIGH** |
| [`COMPILATION.md`](COMPILATION.md) | LaTeX compilation (📦 moved to HAFiscal-dev/docs/project/) | **🟢 REF** |
| [`FIGURE-MANAGEMENT.md`](FIGURE-MANAGEMENT.md) | Figure generation and management workflows | **🟢 REF** |
| [`LATEX-TABLE-PDF-HTML-FORMATTING-GUIDE.md`](LATEX-TABLE-PDF-HTML-FORMATTING-GUIDE.md) | Document formatting details | **🟢 REF** |
| [`DEVELOPMENT_NOTES.md`](DEVELOPMENT_NOTES.md) | Development-only files for reviewer information | **🟢 REF** |
| [`CLAUDE.md`](CLAUDE.md) | AI conversation logs, debugging history | **🟢 REF** |

## 🎯 **AI Quick Navigation**

### **I want to...**

| **Goal** | **Start With** | **Then Read** |
|----------|----------------|----------------|
| 🧠 **Understand the research** | `010_PAPER_ABSTRACT_AND_CLAIMS.md` | `020_RESEARCH_CONTEXT_AND_FINDINGS.md` |
| 📊 **Get key facts quickly** | `SUMMARY.json` | `010_PAPER_ABSTRACT_AND_CLAIMS.md` |
| 📐 **Understand the math model** | `035_MODEL_SUMMARY.md` | `040_MATHEMATICAL_STRUCTURE.md`, `045_EQUATION_MAP.md` |
| 🔢 **Map equations to code** | `045_EQUATION_MAP.md` | `040_MATHEMATICAL_STRUCTURE.md`, `047_STATE_SPACE_AND_FLOW.md` |
| 🔄 **Understand state flow** | `047_STATE_SPACE_AND_FLOW.md` | `040_MATHEMATICAL_STRUCTURE.md` |
| 🤖 **Set up RAG indexing** | `048_RAG_INDEXING_STRATEGY.md` | `040_MATHEMATICAL_STRUCTURE.md`, `045_EQUATION_MAP.md` |
| ⚡ **Run reproduction quickly** | `000_AI_QUICK_START_GUIDE.md` → `./reproduce.sh` | `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` |
| 💻 **Do computational analysis** | `030_COMPUTATIONAL_WORKFLOWS.md` | `060_CODE_NAVIGATION.md` |
| 🎛️ **Use interactive dashboard** | `070_INTERACTIVE_DASHBOARD.md` | `dashboard/DASHBOARD_README.md` |
| 🔍 **Debug issues** | `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` | All others as needed |
| ⚠️ **Fix "undefined ref" warnings** | `SUBFILE_CROSS_REFERENCE_ARCHITECTURE.md` | `EXPECTED_WARNINGS.md` |
| 📊 **Use as REMARK** | `050_REMARK_INTEGRATION_GUIDE.md` | `000_AI_QUICK_START_GUIDE.md` |
| 🏗️ **Build documents** | `COMPILATION.md` (→ HAFiscal-dev) | `FIGURE-MANAGEMENT.md` |
| 🔧 **Control build output** | `BUILD_SYSTEM_VERBOSITY.md` | `EXPECTED_WARNINGS.md` |
| ⚠️ **Understand warnings** | `EXPECTED_WARNINGS.md` | `BUILD_SYSTEM_VERBOSITY.md` |
| 🚀 **Optimize Cursor AI** | `CURSOR_INDEXING_STRATEGY.md` | `.cursorindexingignore` |

## 🤖 **AI System Types & Recommendations**

### **Research/Analysis AI**
**Priority Reading**: `020_RESEARCH_CONTEXT_AND_FINDINGS.md` → `030_COMPUTATIONAL_WORKFLOWS.md`

- Focus on understanding methodology and findings
- Use computational workflows for replication
- Reference troubleshooting for validation

### **Code/Implementation AI**
**Priority Reading**: `030_COMPUTATIONAL_WORKFLOWS.md` → `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`

- Start with computational pipeline understanding
- Use troubleshooting for environment setup
- Reference data dependencies for integration

### **Documentation/Support AI**
**Priority Reading**: `000_AI_QUICK_START_GUIDE.md` → All others

- Comprehensive coverage of all documentation
- Focus on user guidance and troubleshooting
- Use specialized guides for specific questions

### **Validation/Testing AI**
**Priority Reading**: `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` → `050_REMARK_INTEGRATION_GUIDE.md`

- Focus on validation procedures
- Use REMARK standards for compliance checking
- Reference computational workflows for testing

## 📊 **Documentation Quality Metrics**

| **Document** | **Lines** | **Coverage** | **Last Updated** |
|--------------|-----------|--------------|------------------|
| `000_AI_QUICK_START_GUIDE.md` | 150+ | Comprehensive | Latest |
| `020_RESEARCH_CONTEXT_AND_FINDINGS.md` | 200+ | Comprehensive | Latest |
| `030_COMPUTATIONAL_WORKFLOWS.md` | 180+ | Detailed | Latest |
| `080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md` | 200+ | Comprehensive | Latest |
| Other files | Variable | Specialized | Historical |

## 🔄 **Documentation Philosophy**

This AI documentation follows these principles:

### **Hierarchical Information Architecture**

- **000-level**: Entry points and overviews
- **020-050**: Core technical content
- **080+**: Support and troubleshooting
- **Named files**: Specialized/historical content

### **AI-First Design**

- ✅ **Structured format** - Easy parsing and navigation
- ✅ **Clear priorities** - Marked importance levels
- ✅ **Actionable content** - Commands, workflows, procedures
- ✅ **Cross-references** - Linked information architecture
- ✅ **Validation support** - Testing and verification guidance

### **Comprehensive Coverage**

- 🎯 **Research content** - What this repository does
- 🔧 **Technical implementation** - How to use it
- 🛠️ **Operational support** - How to fix issues
- 📈 **Integration guidance** - How it fits in larger ecosystems

## 🚨 **Critical AI Guidelines**

### **Always Start Here**:

1. **Read** `000_AI_QUICK_START_GUIDE.md` first
2. **Identify** your specific AI task type
3. **Follow** the recommended reading sequence
4. **Test** environment before major operations

### **Key Success Patterns**:

- ✅ Use the reproduction script (`./reproduce.sh`) as primary interface
- ✅ Validate environment before computational work
- ✅ Start with quick tests before full replication
- ✅ Reference troubleshooting when issues arise

### **Common AI Failure Modes to Avoid**:

- ❌ Skipping environment validation
- ❌ Attempting full computation without understanding resource requirements
- ❌ Modifying core files without understanding their dependencies and relationships
- ❌ Ignoring computational time requirements (see reproduce/benchmarks/README.md for timing estimates)
- ❌ **Removing `\whenintegrated{}` wrappers from labels** - These are essential architecture, not bugs! See `SUBFILE_CROSS_REFERENCE_ARCHITECTURE.md`
- ❌ **"Fixing" undefined reference warnings on first pass** - These are expected and resolve after multiple compilation passes

---

## 📊 **Structured Metadata**

For machine-readable metadata about this repository, see these files in the repository root:

| File | Format | Purpose |
|------|--------|---------|
| [`../codemeta.json`](../codemeta.json) | CodeMeta | Software metadata for GitHub, Zenodo, citation tools |
| [`../schema.json`](../schema.json) | Schema.org JSON-LD | Structured data for search engines and AI systems |
| [`../CITATION.cff`](../CITATION.cff) | Citation File Format | Citation metadata (authors, title, DOI) |
| [`../LICENSE`](../LICENSE) | Text | Apache 2.0 license terms |

These files are located in the repository root for maximum tool compatibility and discoverability.

---

**🎯 Next Step**: Start with [`000_AI_QUICK_START_GUIDE.md`](000_AI_QUICK_START_GUIDE.md) for your introduction to this research repository.
