# AURIS Engineering Guide

## Identity

The product name is AURIS: Autonomous Understanding and Reasoning Intelligence System. Treat alternate names in imported specifications as naming mistakes. Use only AURIS in runtime copy, code identifiers, paths, and new documentation.

## Architecture

- Keep permission decisions in deterministic code outside any language model.
- Keep device operations typed, allowlisted, visible, auditable, and verifiable.
- Never execute arbitrary shell text generated from a user command.
- Never require administrator privileges for AURIS Foundation capabilities.
- Report unavailable integrations honestly.

## Commands

```powershell
C:\Users\dmodi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1
```

## Definition of Done

Implementation, policy enforcement, input validation, error handling, audit events, verification evidence, tests, and accurate UI status must all exist. A visible control must be functional or explicitly disabled with a reason.
