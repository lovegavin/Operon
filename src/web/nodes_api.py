"""Desktop endpoint: compute-node inventory and free capacity."""
from fastapi import HTTPException

from operon import nodes


def mount_nodes(app, service):
    @app.get('/api/nodes')
    @app.get('/api/v1/nodes')
    def nodes_inventory(refresh: int = 0):
        return nodes.inventory(service, refresh=bool(refresh))

    @app.get('/api/nodes/{key}')
    @app.get('/api/v1/nodes/{key}')
    def node_detail(key: str, refresh: int = 0):
        for item in nodes.inventory(service, refresh=bool(refresh)):
            if item['target'] == key:
                return item
        raise HTTPException(status_code=404, detail='unknown compute node')
