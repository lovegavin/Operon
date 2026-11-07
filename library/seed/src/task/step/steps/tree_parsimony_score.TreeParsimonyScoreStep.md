# Fitch parsimony score of a tree and character matrix

Computes the Fitch parsimony score for a Newick tree and a tip-by-character matrix.

Inputs are tree parameters (Newick string) and, where relevant, a numerical matrix.
The output is a two-dimensional form with the reported statistics.

## Limitations

Newick parsing supports rooted trees with branch lengths; support values and quoted labels are not interpreted.
