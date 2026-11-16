---
name: deepcode-plan-verify
description: Structured codebase indexing, implementation planning, plan review, and post-edit verification distilled from DeepCode.
---

# DeepCode Plan & Verify Workflow

Use this skill for non-trivial engineering tasks requiring multi-file changes or architectural decisions.

## 1. Codebase Indexing
- Locate target modules, entry points, and existing test suites before editing.
- Map data flow and interface contracts across affected boundaries.

## 2. Planning & Plan Review
- Break the task into ordered, minimal, independently verifiable steps.
- Verify every planned change respects workspace isolation, cross-platform paths, and existing public interfaces.
- Identify edge cases and rollback/failure modes before writing code.

## 3. Implementation
- Implement one logical module at a time, reusing existing helpers and avoiding duplicated logic.
- Keep edits local and preserve unrelated comments/docstrings.

## 4. Verification
- Run unit tests and type/lint checks covering all modified paths.
- Confirm every requirement and edge case is backed by observed command output before reporting completion.
