# Operon Studio 5.7.27

Release date: 2026-11-22

This release fixes how the runtime panel reports a healthy environment that has an
optional binding left out, and makes the number of parallel tasks a user setting
instead of a per-graph field that defaulted to 2 everywhere.

## Fixed

- **An environment with optional bindings no longer reads as incomplete.**
  `core` installs 66 required dependencies and one optional binding (`vina`), and the
  panel showed `依赖缺失 1` on a ready environment because the readiness rule compared
  `dependency_installed` against a total that also counted optional rows. Dependency
  counting now separates required from optional rows in `operon/environment_install.py`
  (`_split_dependency_counts`) and in the desktop-API copy `src/web/environment_api.py`,
  so the panel's `dependency-gap` state only fires when a required dependency is
  missing. Optional gaps keep their own fields (`optional_total`, `optional_installed`,
  `optional_missing`) and are still reported, just not as a defect.

## Added

- **Default parallel tasks is a setting.** Settings → 执行 exposes a number (1–64).
  The value is stored in the desktop preferences file and applied when a graph does
  not carry its own `max_parallel_tasks`: `src/web/execution_plan.py` falls back to
  `default_parallel_tasks()` in `settings()`, and `mount_preferences` keeps that
  fallback in sync on startup and on save. A graph that sets the field still wins.
  Leaving the field empty keeps the built-in default of 2.

## Library

Library `main-v1.1.16` is unchanged in this release.
