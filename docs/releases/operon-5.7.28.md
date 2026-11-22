# Operon Studio 5.7.28

Release date: 2026-11-22

This release replaces the cramped inline control under Settings → 执行 with a proper
settings row. Nothing in the runtime changed; the number of parallel tasks, its
storage and its fallback rule are the ones introduced in 5.7.27.

## Fixed

- **The concurrency field is a readable row instead of three squeezed lines.**
  The section used a `legend`, a hint paragraph and one inline `label` whose input sat
  against the hint text, so the label, the input and the hint collapsed into each other
  at the default dialog width. The section is now a heading, one line of explanation
  and a card: the left side carries the field name and its range, the right side the
  number input (`frontend/src/ConcurrencySettings.tsx`, `frontend/src/settings.css`).
  Measured in the installed build: the card is 560×75 with 16px padding and a 20px gap,
  the input is 88×39 and right aligned, and the section does not scroll horizontally.

## Library

Library `main-v1.1.16` is unchanged in this release.
