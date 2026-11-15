"""Bound recursive graph expansion before copying or compiling node metadata."""
from operon.contracts.base import ContractError


def check_graph_size(graph, *, max_nodes=4096, max_edges=16384, max_depth=6):
    stack, nodes, edges = [(graph, 0)], 0, 0
    def field(value, name, default=None):
        return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)
    while stack:
        current, depth = stack.pop()
        entries = field(current, 'nodes', ())
        connections = field(current, 'edges', ())
        if not isinstance(entries, (list, tuple)) or not isinstance(connections, (list, tuple)):
            raise ContractError('Workflow nodes and edges must be arrays', code='invalid_workflow')
        nodes += len(entries)
        edges += len(connections)
        if depth > max_depth or nodes > max_nodes or edges > max_edges:
            raise ContractError('Workflow exceeds its expanded graph limits; split it into smaller runs',
                                code='payload_too_large', details={
                                    'max_nodes': max_nodes, 'max_edges': max_edges, 'max_depth': max_depth})
        for node in entries:
            route = field(node, 'route')
            if route is not None:
                stack.append((field(route, 'graph'), depth + 1))
