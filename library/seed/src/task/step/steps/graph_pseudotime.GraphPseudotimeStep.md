# Graph pseudotime

Geodesic pseudotime from a principal-component k-nearest-neighbour graph.

## Purpose

Implements `graph_pseudotime` as a trajectory-inference operator. The operator
projects the input cell-by-gene table onto its leading principal components,
builds a k-nearest-neighbour graph in that space, computes shortest-path
geodesic distances from a root cell and rescales them to the unit interval.
It returns the pseudotime together with the first two diffusion-map coordinates
used for visualisation.

## Parameters

`n_components` sets the number of principal components, `n_neighbors` the graph
degree and `root_cell` the zero-based row index of the root. `row_dim`/`field_dim`
name the input axes and `output` is injected by the engine.

## Output

A Form indexed by cell with columns `pseudotime`, `dc1` and `dc2`. Pseudotime is
zero at the root and one at the most distant reachable cell.

## Limitations

The graph is built on a Euclidean PCA embedding, so strongly non-linear or
disconnected manifolds can fold. Unreachable cells keep the maximum finite
distance. The root is supplied by the caller rather than inferred.
