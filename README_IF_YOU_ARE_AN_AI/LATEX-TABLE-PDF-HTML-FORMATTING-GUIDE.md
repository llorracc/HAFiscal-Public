# LaTeX Table & Figure PDF/HTML Formatting Guide

**Latest Update:** September 13, 2025  
**Purpose:** Unified style guide for both Tables/*.tex and Figures/*.tex files  

---

## 🎯 Unified Style Principles

### 1. File Structure Standards

#### Header Template (Both Tables & Figures)
```latex
\input{./_path-to-root.ltx}
\documentclass[\PathToRoot/\ProjectName]{subfiles}

% For tables only:
\standaloneTableSetup

% For figures only: 
% (No specific setup command needed)

\begin{document}
```

#### Footer Template (Both Tables & Figures)
```latex
% Smart bibliography: Only include bibliography if standalone AND has citations
\smartbib

\end{document}
```

### 2. Container Harmonization

#### Table Containers
```latex
% TAXONOMY: table-container harmonization - ORIGINAL: \begin{table}[p]
\begin{table}[tb]  % Standardized placement: top/bottom only
  \centering
  \caption{Your Table Caption}
  \whenintegrated{\label{tab:yourlabel}} % integrated doc: SST for labels
  
  % Table content here
  
\end{table}
```

#### Figure Containers  
```latex
\begin{figure}[htb]  % here, top, bottom placement
  \centering
  \caption{Your Figure Caption}
  \whenintegrated{\label{fig:yourlabel}} % integrated doc: SST for labels
  
  % Figure content here
  
\end{figure}
```

### 3. Responsive Table Structure

#### Single Panel Tables
```latex
\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcr@{}}
  Parameter & Notation & Value \\ \hline
  % Table rows here
  \hline
  \multicolumn{3}{l}{%
    \footnotesize Your footnote text here.
  } \\
\end{tabular*}
```

#### Multi-Panel Tables
```latex
% Panel A
\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcr@{}}
  \multicolumn{3}{c}{\small Panel A: Panel Description} \\
  \addlinespace
  \hline
  % Panel A content
  \hline
  \multicolumn{3}{l}{%
    \footnotesize Panel A footnote.
  } \\
  \multicolumn{3}{l}{\textcolor{white}{.}} \\  % Spacer
\end{tabular*}

\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccc@{}}
  \multicolumn{4}{c}{\small Panel B: Panel Description} \\
  \addlinespace
  \hline
  % Panel B content
  \hline
  \multicolumn{4}{l}{%
    \footnotesize Panel B footnote.
  } \\
\end{tabular*}
```

### 4. Figure Structure Standards

#### Single Figure
```latex
\includegraphics[width=.9\textwidth]{\PathToRoot/Figures/your-figure-file}

\medskip
\noindent\hfill\parbox{0.9\textwidth}{\footnotesize
  \textbf{Note}: Your detailed figure note here.
}\hfill
```

#### Multi-Panel Figures (Subfigures)
```latex
\begin{subfigure}[b]{.33\linewidth}
  \centering
  \includegraphics[width=\linewidth]{\PathToRoot/Path/to/subfigure1}
  \caption{Subfigure caption}
  \whenintegrated{\label{fig:subfig1}} % integrated doc: SST for labels
\end{subfigure}%
\begin{subfigure}[b]{.33\linewidth}
  \centering
  \includegraphics[width=\linewidth]{\PathToRoot/Path/to/subfigure2}
  \caption{Subfigure caption}
  \whenintegrated{\label{fig:subfig2}} % integrated doc: SST for labels
\end{subfigure}%

\medskip
\noindent\hfill\parbox{0.9\textwidth}{\footnotesize
  \textbf{Note}: Your detailed figure note referencing subfigures.
}\hfill
```

---

## 🛠 Specific Improvements to Apply

### From Tables to Figures

#### 1. Missing Structure Elements in Figures
- **Add taxonomy comments**: Document changes made (like table-container harmonization)
- **Standardize placement**: Use `[htb]` consistently
- **Add improvement tracking**: Comments about what was changed and when

#### 2. Enhanced Note Formatting
**Current Figure Style (Good):**
```latex
\noindent\hfill\parbox{0.9\textwidth}{\footnotesize
  \textbf{Note}: Figure explanation.
}\hfill
```

**Enhanced Style (Apply to Both):**
```latex
\vspace{0.5em}
\noindent\parbox{\textwidth}{\footnotesize 
  \textbf{Note}: Figure explanation with proper full-width formatting.
}
\vspace{0.5em}
```

#### 3. Cross-Reference Standards
**Both Tables & Figures:**
- Use `\whenintegrated{\label{tab:name}}` for tables
- Use `\whenintegrated{\label{fig:name}}` for figures  
- Reference with `Section~\ref{sec:name}` or `\citet{reference}`

#### 4. Path Consistency  
**Always use `\PathToRoot` prefix:**
```latex
% Good:
\includegraphics[width=.9\textwidth]{\PathToRoot/Figures/filename}

% Bad:  
\includegraphics[width=.9\textwidth]{../Figures/filename}
```

### New Standards for Figures

#### 1. Figure Container Taxonomy
Add taxonomy comment for figure harmonization:
```latex
\begin{figure}[htb] % TAXONOMY: figure-container harmonization - ORIGINAL: \begin{figure}[h]
```

#### 2. Caption Standards
```latex
% Table captions: Above content
\caption{Table Title}
\whenintegrated{\label{tab:name}}

% Figure captions: Above content  
\caption{Figure Title}  
\whenintegrated{\label{fig:name}}
```

#### 3. Standalone Figure Setup
Consider adding equivalent to `\standaloneTableSetup` for figures:
```latex
% For figures only (new addition):
% \standaloneFigureSetup % TODO: Define if needed for special figure formatting
```

---

## 📋 HTML Compatibility Requirements

### 1. tex4ht Compatibility
- **Tables**: Use `\hline` not `\toprule`/`\midrule`/`\bottomrule` [[memory:8871619]]
- **Figures**: SVG graphics work well with tex4ht
- **Both**: Avoid fixed widths that break responsive design

### 2. CSS Integration
- Tables and figures inherit from `econ-ark-html-theme.css`
- Individual CSS files generated for complex formatting
- Dark mode support: `@media (prefers-color-scheme: dark)`

### 3. Bibliography Handling
**Smart bibliography for both:**
```latex
\smartbib
```

---

## 🎨 Typography & Formatting Standards

### 1. Font Sizing Hierarchy
- **Main caption**: Default size
- **Panel headers**: `\small`
- **Table content**: Default size
- **Notes**: `\footnotesize` or `\scriptsize`

### 2. Spacing Standards
- **Between panels**: `\vspace{1em}`
- **Around notes**: `\vspace{0.5em}`
- **Table spacing**: `\addlinespace` after headers

### 3. Alignment Standards
- **Tables**: Use column specifications (`lcr`, `lccc@{}`, etc.)
- **Figures**: `\centering` for main content
- **Notes**: `\parbox` with appropriate width

---

## 🚀 Implementation Checklist

### For Each Table File
- [ ] Standardized header with emacs hint
- [ ] `\standaloneTableSetup` included
- [ ] Container harmonization: `[tb]` placement
- [ ] Integrated doc labels: `\whenintegrated{\label{tab:name}}`
- [ ] Responsive width: `\textwidth` with `@{\extracolsep{\fill}}`
- [ ] Panel structure with multicolumn headers
- [ ] Footnotes using `\parbox` with proper sizing
- [ ] Smart bibliography: `\smartbib`
- [ ] Taxonomy comments documenting changes

### For Each Figure File  
- [ ] Standardized header with emacs hint
- [ ] Container harmonization: `[htb]` placement
- [ ] Integrated doc labels: `\whenintegrated{\label{fig:name}}`
- [ ] Consistent path usage: `\PathToRoot` prefix
- [ ] Proper subfigure structure if multi-panel
- [ ] Enhanced note formatting with `\parbox`
- [ ] Smart bibliography: `\smartbib`
- [ ] Taxonomy comments documenting changes (NEW)

### Cross-File Consistency
- [ ] All `\PathToRoot` paths work correctly
- [ ] Labels follow naming conventions (`tab:` vs `fig:`)  
- [ ] References use consistent formatting
- [ ] Bibliography handling is uniform

---

## 📚 Examples & Templates

### Complete Table Template
```latex
% -*- mode: LaTeX; TeX-PDF-mode: t; -*- # Tell emacs the file type (for syntax)
\input{./_path-to-root.ltx}
\documentclass[\PathToRoot/\ProjectName]{subfiles}

\standaloneTableSetup

\begin{document}

\begin{table}[tb] % TAXONOMY: table-container harmonization - ORIGINAL: \begin{table}[p]
  \centering
  \caption{Your Table Title}
  \whenintegrated{\label{tab:yourtable}}

  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcr@{}}
    \hline
    Column 1 & Column 2 & Column 3 \\ \hline
    Data 1   & Data 2   & Data 3   \\
    \hline
    \multicolumn{3}{l}{%
      \footnotesize Note: Your table note here.
    } \\
  \end{tabular*}
\end{table}

% Smart bibliography: Only include bibliography if standalone AND has citations
\smartbib

\end{document}
```

### Complete Figure Template
```latex
% -*- mode: LaTeX; TeX-PDF-mode: t; -*-
\input{./_path-to-root.ltx}
\documentclass[\PathToRoot/\ProjectName]{subfiles}

\begin{document}

\begin{figure}[htb] % TAXONOMY: figure-container harmonization - ORIGINAL: \begin{figure}[h]
  \centering
  \caption{Your Figure Title}
  \whenintegrated{\label{fig:yourfigure}}
  \includegraphics[width=.9\textwidth]{\PathToRoot/Figures/your-figure-file}
  
  \medskip
  \noindent\hfill\parbox{0.9\textwidth}{\footnotesize
    \textbf{Note}: Your figure explanation with proper formatting.
  }\hfill
\end{figure}

% Smart bibliography: Only include bibliography if standalone AND has citations  
\smartbib

\end{document}
```

---

**Next Steps**: Apply these unified standards systematically to all Figures/*.tex files to match the improvements already made to Tables/*.tex files. 
