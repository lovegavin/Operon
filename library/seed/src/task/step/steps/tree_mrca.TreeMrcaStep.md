# Most recent common ancestor of two tips

## Purpose

Finds the MRCA node of two tip labels in a Newick tree and reports its height and pairwise distance.

Inputs are tree parameters (Newick string) and, where relevant, a numerical matrix.
The output is a two-dimensional form with the reported statistics.

## Limitations

Newick parsing supports rooted trees with branch lengths; support values and quoted labels are not interpreted.
