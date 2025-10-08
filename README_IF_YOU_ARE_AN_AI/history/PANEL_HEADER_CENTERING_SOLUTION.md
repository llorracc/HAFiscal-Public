# Panel Header Centering Solution

## Problem Identified
Panel headers ("Panel A:", "Panel B:") and table footer notes were using different CSS classes but both left-aligned:
- **Panel Headers**: `<span class='ec-lmbx-12'>Panel A: Parameters that apply to all types</span>` (bold, left-aligned)
- **Footer Notes**: `<span class='ec-lmr-10'>Panel (A) shows parameters...</span>` (regular, left-aligned)

## Solution Implemented
Modified LaTeX source to wrap panel headers in `\begin{center}...\end{center}` environment:

### Files Modified:
1. Tables/calibration.tex
2. Tables/calibrationRecession.tex  
3. Tables/estimBetas.tex
4. Tables/nonTargetedMoments.tex
5. Tables/nonTargetedMoments_wSplZero.tex

### Change Pattern:
```latex
% BEFORE
\textbf{Panel A: Parameters that apply to all types}

% AFTER
\begin{center}
  \textbf{Panel A: Parameters that apply to all types}
\end{center}
```

## Result
- Panel headers now generate HTML with center div wrappers
- Footer notes remain left-aligned as intended
- Independent CSS control is now possible

## Testing
- PDF compilation: ✅ Success
- HTML generation: ✅ Success  
- Panel headers centered: ✅ Confirmed in HTML structure 