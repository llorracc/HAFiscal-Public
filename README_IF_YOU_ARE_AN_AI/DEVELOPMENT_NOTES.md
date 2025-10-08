# Development Notes

## Development-Only Files

The following files/directories are specific to the development environment and can be ignored by journal reviewers:

- `prompts/` (symlink) → Development prompts and AI assistant configurations
- `Tools/` (symlink) → Development utilities and helper scripts  
- `.dir-locals.el` → Emacs editor configuration
- `@resources-update-from-remote_private.sh` → Development sync script

These symlinks point to the developer's local filesystem and will not work on other systems.

## For Journal Reviewers

All essential functionality is contained in the main repository files. The reproduction scripts (`reproduce.sh`) and main documents (`HAFiscal.pdf`, `HAFiscal-Slides.pdf`) do not depend on these development-only files.
