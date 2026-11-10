# Ultrametricity check for a dated tree

## Purpose

Tests whether all root-to-tip distances are equal within a tolerance.

Inputs are tree parameters (Newick string) and, where relevant, a numerical matrix.
The output is a two-dimensional form with the reported statistics.

## Limitations

Newick parsing supports rooted trees with branch lengths; support values and quoted labels are not interpreted.
