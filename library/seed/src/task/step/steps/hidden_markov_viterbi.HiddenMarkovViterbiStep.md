# Viterbi decoding for a discrete hidden Markov model

## Purpose

Most probable hidden state path for a discrete-emission HMM.

## Inputs

A numeric table whose columns are consumed positionally; the first column is the row label when the reader drops it.

## Parameters

See the adjacent parameter JSON. Dimensions default to `row`/`field`.

## Limitations

Synthetic or small tabular inputs are intended for deterministic verification; this is not a replacement for a full probabilistic-programming workflow.
