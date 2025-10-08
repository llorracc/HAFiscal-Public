# Figure Management System

This document explains HAFiscal's sophisticated figure management system, which uses symbolic links and portable path macros to enable flexible figure referencing across different compilation contexts.

## System Overview

The HAFiscal figure management system implements two key technologies:

1. **Symlink-Based Organization**: Figures in `Figures/` are symbolic links to original sources
2. **Portable Path System**: `\PathToRoot` macro system enables context-aware path resolution

This architecture eliminates file duplication while ensuring compatibility across different environments (local TeXLive, Overleaf, GitHub Actions).

## Symlink Organization

### Structure
```
Figures/                                    # Central figure repository
├── _path-to-root.ltx.tex                       # Path resolution configuration
├── figure-name.pdf -> ../Code/HA-Models/...# Symlinks to original figures  
├── figure-name.png -> ../Code/HA-Models/...
├── figure-name.jpg -> ../Code/HA-Models/...
└── figure-name.svg -> ../Code/HA-Models/...
```

### Benefits of Symlink System

1. **Single Source of Truth**: Figures are generated once in their computational location
2. **No Duplication**: Eliminates duplicate figure files and storage overhead
3. **Automatic Updates**: Changes to generated figures immediately reflect in LaTeX compilation
4. **Version Control Efficiency**: Git tracks symlinks (small) instead of binary files (large)
5. **Multi-Format Support**: Each figure available in multiple formats (PDF, PNG, JPG, SVG)

### Symlink Examples
```bash
# Typical symlink structure in Figures/
AggMPC_LotteryWin_comparison.pdf -> ../Code/HA-Models/Target_AggMPCX_LiquWealth/Figures/AggMPC_LotteryWin_comparison.pdf
AggMPC_LotteryWin_comparison.png -> ../Code/HA-Models/Target_AggMPCX_LiquWealth/Figures/AggMPC_LotteryWin_comparison.png
Cumulative_multiplier_Check.jpg -> ../Code/HA-Models/FromPandemicCode/Figures/Cumulative_multiplier_Check.jpg
```

## Portable Path System

### The `\PathToRoot` Macro

The system uses `\PathToRoot` to provide relative path resolution from any directory:

```latex
% In Figures/_path-to-root.ltx.tex
\providecommand{\PathToRoot}{}\renewcommand{\PathToRoot}{..}
\providecommand{\PathsToInputs}{}\renewcommand{\PathsToInputs}{_paths-to-inputs.ltx}
\input{\PathToRoot/\PathsToInputs}
```

### Path Definitions

In `@local/_paths-to-inputs.ltx`:
```latex
\providecommand{\CodeDir}{\PathToRoot/Code}
\providecommand{\DataDir}{\PathToRoot/Data}  
\providecommand{\FigsDir}{\PathToRoot/Figures}
\providecommand{\TableDir}{\PathToRoot/Tables}
\providecommand{\ApndxDir}{\PathToRoot/Appendices}
```

### Usage in LaTeX Documents

```latex
% Portable figure inclusion
\includegraphics{\FigsDir/figure-name.pdf}

% Works from any directory because \FigsDir resolves correctly
% - From root: \FigsDir = Figures/
% - From Subfiles/: \FigsDir = ../Figures/
% - From Tables/: \FigsDir = ../Figures/
```

## Environment Compatibility

### Local TeXLive Systems
- Full symlink support 
- Figures resolve directly to source locations
- No file copying required
- Development workflow optimized

### Overleaf Compatibility  
- Symlinks prohibited by Overleaf
- System designed to work with copied figures as fallback
- Path macros ensure LaTeX code remains identical
- Upload process can replace symlinks with actual files

### GitHub Actions CI/CD
- Symlinks work correctly in Linux containers
- Automated builds have access to both figure sources and symlinks
- No special handling required for CI environments

### GitHub Pages Deployment
- Symlink resolution handled during build process
- Static HTML generation includes figures from resolved paths
- No symlink dependencies in final deployed site

## Figure Generation Workflow

### Computational Figure Sources

Figures are generated in their computational contexts:

```
Code/HA-Models/
├── Target_AggMPCX_LiquWealth/Figures/    # Estimation result figures
├── FromPandemicCode/Figures/             # Policy analysis figures  
├── FromPandemicCode/Tables/              # Generated table figures
└── Other computational modules...
```

### Symlink Creation Process

When new figures are generated:

1. **Figure Generation**: Python/computational scripts create figures in source locations
2. **Symlink Creation**: Link created in `Figures/` pointing to source
3. **LaTeX Integration**: Figure immediately available for inclusion via `\FigsDir` paths
4. **Format Support**: Multiple formats (PDF, PNG, SVG) linked automatically

### Example Symlink Creation
```bash
cd Figures/
ln -s ../Code/HA-Models/FromPandemicCode/Figures/new-figure.pdf new-figure.pdf
ln -s ../Code/HA-Models/FromPandemicCode/Figures/new-figure.png new-figure.png  
```

## LaTeX Integration Patterns

### Standard Figure Inclusion
```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.8\textwidth]{\FigsDir/AggMPC_LotteryWin_comparison.pdf}
\caption{Aggregate MPC Comparison}
\label{fig:aggmpc}
\end{figure}
```

### Conditional Format Selection
```latex
% PDF/HTML conditional figure formats
\weborpdf{
  \includegraphics{\FigsDir/figure-name.svg}  % SVG for HTML
}{
  \includegraphics{\FigsDir/figure-name.pdf}  % PDF for LaTeX
}
```

### Multi-Panel Figures
```latex
\begin{figure}[htbp]
\centering
\subfloat[Panel A]{\includegraphics[width=0.45\textwidth]{\FigsDir/panel-a.pdf}}
\hfill
\subfloat[Panel B]{\includegraphics[width=0.45\textwidth]{\FigsDir/panel-b.pdf}}
\caption{Multi-panel figure using symlinked sources}
\end{figure}
```

## Directory Structure Integration

### Root Directory Files
- `HAFiscal.tex`: Uses `\FigsDir/` paths directly
- `HAFiscal-Slides.tex`: Same path system for presentations

### Subfiles Directory
- Each subfile loads `\PathToRoot` and path definitions
- `\FigsDir` resolves to `../Figures/` automatically
- No path changes needed when moving between compilation contexts

### Tables Directory  
- Can reference figures using same `\FigsDir` macro system
- Maintains portability across different compilation locations

## Maintenance and Best Practices

### Adding New Figures

1. **Generate in Source Location**: Create figures in appropriate `Code/` subdirectory
2. **Create Symlinks**: Link all relevant formats to `Figures/`
3. **Use Portable Paths**: Always reference via `\FigsDir/` in LaTeX
4. **Test Compilation**: Verify figures work in different compilation contexts

### Symlink Management

```bash
# Check symlink integrity
find Figures/ -type l -exec ls -l {} \; | grep -v "^l"  # Find broken symlinks

# Verify figure availability
ls -la Figures/*.pdf | head -10                         # Check PDF figures
ls -la Figures/*.png | head -10                         # Check PNG figures
```

### Path System Maintenance

- **Never hardcode paths** in LaTeX files
- **Always use `\FigsDir/` prefix** for figure references  
- **Test from multiple directories** to verify path resolution
- **Update `_path-to-root.ltx.tex`** if directory relationships change

## Troubleshooting

### Common Issues

**Problem**: Figure not found during compilation
```
LaTeX Error: File 'Figures/figure-name.pdf' not found
```
**Solutions**: 
1. Verify symlink exists: `ls -la Figures/figure-name.pdf`
2. Check symlink target: `readlink Figures/figure-name.pdf`  
3. Ensure source figure was generated: `ls -la Code/HA-Models/.../figure-name.pdf`

**Problem**: Symlinks not working in environment
**Solutions**:
1. For Overleaf: Copy actual figures instead of using symlinks
2. For Windows: Ensure symlink support enabled or copy figures
3. For CI: Verify container has symlink support

**Problem**: Path resolution incorrect
**Solutions**:
1. Check `_path-to-root.ltx.tex` relative path from current directory
2. Verify `\PathsToInputs` points to correct configuration file
3. Test `\FigsDir` macro expansion in different compilation contexts

### Debugging Commands

```bash
# Test symlink integrity
find Figures/ -type l ! -exec test -e {} \; -print

# Verify path macro system
grep -r "FigsDir" Subfiles/                  # Check usage patterns
grep -r "PathToRoot" @local/                # Check path definitions
```

This figure management system provides the flexibility needed for academic paper workflows while maintaining compatibility across different LaTeX environments and deployment contexts. 