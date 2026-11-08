# Flux balance analysis

## Purpose

Solve a steady-state flux balance linear program from a stoichiometric matrix and bounds.

## Parameters

See `fba_flux_balance.FbaFluxBalanceStep.parameters.json`; `row_dim` and `field_dim` name the input axes.

## Limitations

Deterministic closed-form implementation on the stated inputs; no model training or parameter estimation beyond least squares / linear programming.
