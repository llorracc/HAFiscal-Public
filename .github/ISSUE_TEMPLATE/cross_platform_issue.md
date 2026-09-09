---
name: Cross-Platform Issue
about: Report platform-specific problems (macOS, Linux, WSL2)
title: '[PLATFORM] '
labels: cross-platform
assignees: ''
---

## Platform Information

**Operating System:** (e.g., macOS 14.0, Ubuntu 22.04, Windows 11 WSL2)  
**Architecture:** (Intel x86_64, Apple Silicon ARM64, other)  
**Shell:** (bash, zsh, fish)  
**Python Version:** (run `python --version`)  
**Environment Manager:** (UV or Conda)

## Issue Description

Clear description of the platform-specific issue.

## Works On

Which platforms have you tested this on?

- [ ] macOS - ✅ Works / ❌ Fails
- [ ] Linux (Ubuntu) - ✅ Works / ❌ Fails
- [ ] Linux (other distro: _____) - ✅ Works / ❌ Fails
- [ ] Windows WSL2 - ✅ Works / ❌ Fails
- [ ] Windows (native) - ⚠️ Not officially supported

## Steps to Reproduce

1. Run command '...'
2. See error/unexpected behavior

## Expected Behavior

What happens on working platforms?

## Actual Behavior

What happens on the failing platform?

## Error Messages

```
Full error messages
```

## Path Information

If the issue involves file paths, provide:

- Working directory: `pwd`
- Repository location
- Any paths used in commands

## Cross-Platform Test Results

Have you run the cross-platform tests?

```bash
./reproduce/test-cross-platform.sh
```

**Result:** (✅ Pass / ❌ Fail)

## Attempted Solutions

- [ ] Checked [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)
- [ ] Checked [reproduce/TESTING-CROSS-PLATFORM.md](../../reproduce/TESTING-CROSS-PLATFORM.md)
- [ ] Verified file permissions (`chmod +x` for scripts)
- [ ] Checked line endings (should be LF, not CRLF)
- [ ] Other (describe):

## Additional Context

Any other platform-specific details that might be relevant.

## Checklist

- [ ] I have tested on multiple platforms to confirm it's platform-specific
- [ ] I have run the cross-platform compatibility test
- [ ] I have provided complete platform information
- [ ] I have checked existing platform-specific issues
