"""Portable route snapshots, saved workflows, and expansion into the existing DAG.

Saving a workflow never registers it. The registry contains explicitly selected
snapshots; a running graph is self-contained and does not resolve mutable names.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import uuid

from .storage import FileLock, atomic_json
from operon.parameter_values import read_values
from .parameters import freeze_graph, split_graph, restore_graph, split_execution, restore_execution

from .models import (Graph, GraphEdge, RouteDefinition, RouteInterface, RouteInput,
                     RouteOutput, SavedWorkflow, Workspace, LibraryState)


from operon.planning.route_expansion import (fail, port_index, output_names, require_route,
    check_interface, prepare_interface, expand_routes)


class RouteLibrary:
    def __init__(self, directory, catalog, root, catalog_for=None, *, input_roots=None):
        self.directory, self.catalog, self.root = Path(directory), catalog, root
        self.input_roots = input_roots
        self.catalog_for = catalog_for or (lambda graph: self.catalog)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.directory / ".library.lock")
        self.saved, self.registered = {}, {}
        self.revision = None
        with self.lock:
            self._reload(force=True)

    def _reload(self, force=False):
        revision = self.directory / "revision.json"
        stamp = revision.read_text(encoding="utf-8") if revision.exists() else ""
        if not force and stamp == self.revision:
            return
        saved, registered = {}, {}
        # Scan on startup or after a writer changes the revision; ordinary reads
        # check one tiny revision file, without rescanning operator modules.
        for path in self.directory.glob("route_*.json"):
            try:
                item = SavedWorkflow.model_validate_json(path.read_text(encoding="utf-8"))
                if item.execution_file:
                    item.graph = Graph.model_validate(restore_execution(item.graph.model_dump(mode="json"),
                                                     read_values(self.directory, item.execution_file)))
                if item.parameters_file:
                    item.graph = restore_graph(item.graph.model_dump(mode="json"),
                                               read_values(self.directory, item.parameters_file))
                saved[item.id] = item
            except (ValueError, OSError) as error:
                raise ValueError(f"无法读取保存的路线，原文件已保留：{path}") from error
        index = self.directory / "registry.json"
        if index.exists():
            try:
                registered = {item.id: item for value in json.loads(index.read_text(encoding="utf-8"))
                              if (item := RouteDefinition.model_validate(value))}
            except (ValueError, OSError, TypeError) as error:
                raise ValueError(f"路线注册表损坏，原文件已保留：{index}") from error
        self.saved, self.registered, self.revision = saved, registered, stamp

    def changed(self):
        atomic_json(self.directory / "revision.json", uuid.uuid4().hex)
        self.revision = None

    def _write(self, path, value):
        atomic_json(path, value)

    def _write_saved(self, item):
        topology, values = split_graph(item.graph)
        topology, execution = split_execution(topology)
        item.parameters_file = f"parameters/{item.id}/v{item.version}.json"
        item.execution_file = f"execution/{item.id}/v{item.version}.json"
        # Publish the values first. Replacing the route record is the commit
        # point; an interrupted save leaves the previous version usable.
        self._write(self.directory / item.parameters_file, values)
        self._write(self.directory / item.execution_file, execution)
        record = item.model_dump(mode="json")
        record["graph"] = topology
        self._write(self.directory / f"{item.id}.json", record)

    def list_saved(self):
        with self.lock:
            self._reload()
            return [{"id": item.id, "version": item.version, "name": item.graph.name, "updated_at": item.updated_at,
                     "nodes": len(item.graph.nodes), "interface": item.graph.interface.model_dump() if item.graph.interface else None,
                     "registered_version": self.registered[item.id].version if item.id in self.registered else None}
                    for item in sorted(self.saved.values(), key=lambda item: item.updated_at, reverse=True)]

    def routes(self):
        with self.lock:
            self._reload()
            return [item.model_dump(mode="json") for item in self.registered.values()]

    def get(self, key):
        with self.lock:
            self._reload()
            if key not in self.saved:
                raise KeyError("找不到已保存的路线。")
            return self.saved[key].model_dump(mode="json")

    def save(self, payload):
        catalog = self.catalog_for(payload.graph)
        graph = prepare_interface(freeze_graph(payload.graph, catalog, self.root, input_roots=self.input_roots),
                                  catalog, self.root, input_roots=self.input_roots)
        with self.lock:
            self._reload(force=True)
            key = payload.id or "route_" + uuid.uuid4().hex[:12]
            previous = self.saved.get(key)
            if payload.id and previous is None:
                raise KeyError("原路线已不存在，请另存为新路线。")
            if previous and payload.expected_version != previous.version:
                fail("路线已在其他页面更新，请重新打开或另存为，避免覆盖。")
            item = SavedWorkflow(id=key, version=previous.version + 1 if previous else 1,
                                 updated_at=datetime.now(timezone.utc).isoformat(), graph=graph)
            self._write_saved(item)
            self.saved[key] = item
            self.changed()
            return item.model_dump(mode="json")

    def register(self, keys):
        from .graph import compile_graph
        with self.lock:
            self._reload(force=True)
            additions = {}
            for key in dict.fromkeys(keys):
                if key not in self.saved:
                    raise KeyError("找不到待注册的路线。")
                item = self.saved[key]
                catalog = self.catalog_for(item.graph)
                check_interface(item.graph, catalog)
                # Original files can be missing on another machine. Registration
                # validates the graph using harmless virtual source paths.
                checked = item.graph.model_copy(deep=True)
                from src.reader import primary_ext
                for node in checked.nodes:
                    if node.kind == "source" and node.source is not None:
                        from operon.reader_selection import candidates
                        choices = candidates(catalog['readers'], node.source.path, node.source.reader)
                        if len(choices) > 1 and node.source.dims:
                            wanted = len(node.source.dims)
                            narrowed = [item for item in choices
                                        if (item.get('contracts') or {}).get('output', {}).get('ndim') == wanted]
                            if narrowed:
                                choices = narrowed
                        if len(choices) > 1:
                            from .graph import GraphError
                            raise GraphError('Choose a Reader for input ' + node.id + '; multiple Readers match: '
                                             + ', '.join(item['id'] for item in choices), node.id)
                        # Preserve the declared reader contract (e.g. VCF
                        # genotype metadata); only replace the file location.
                        node.source.path = "route-input" + primary_ext(Path(node.source.path))
                compile_graph(checked, catalog, self.root, input_roots=self.input_roots)
                additions[key] = RouteDefinition(id=key, version=item.version, name=item.graph.name, graph=item.graph)
            updated = {**self.registered, **additions}
            self._write(self.directory / "registry.json", [item.model_dump(mode="json") for item in updated.values()])
            self.registered = updated
            state = self.library_state()
            state["disabled"] = [key for key in state["disabled"] if key not in additions]
            self._write(self.directory / "library_state.json", state)
            self.changed()
            return self.routes()

    def library_state(self):
        with self.lock:
            path = self.directory / "library_state.json"
            return (LibraryState.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.exists() else LibraryState()).model_dump()

    def manage_item(self, key, action):
        with self.lock:
            self._reload(force=True)
            atomic = {item["id"] for item in self.catalog["operators"]}
            if key not in atomic and key not in self.registered:
                raise KeyError("算子已不存在，请刷新算子库。")
            state = self.library_state()
            disabled, hidden = set(state["disabled"]), set(state["hidden"])
            if action == "disable":
                disabled.add(key)
            elif action == "enable":
                disabled.discard(key)
            elif action == "restore":
                hidden.discard(key); disabled.discard(key)
            elif action == "delete":
                disabled.discard(key)
                if key in self.registered:
                    self.registered.pop(key)
                    self._write(self.directory / "registry.json", [r.model_dump(mode="json") for r in self.registered.values()])
                else:
                    hidden.add(key)
            else:
                fail("不支持的算子库操作。")
            self._write(self.directory / "library_state.json", {"disabled": sorted(disabled), "hidden": sorted(hidden)})
            self.changed()
            return {"routes": self.routes(), "state": self.library_state()}

    def install_builtins(self):
        """Seed shipped routes once. Removal/disable and user edits survive boots."""
        from operon.library_location import asset_path
        path = asset_path('src/web/builtin_routes.json')
        bundle = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'routes': []}
        with self.lock:
            self._reload(force=True)
            receipt = self.directory / "builtins_installed.json"
            installed = set(json.loads(receipt.read_text(encoding="utf-8"))) if receipt.exists() else set()
            pending = [RouteDefinition.model_validate(value) for value in bundle["routes"] if value["id"] not in installed]
            if not pending:
                return
            for item in pending:
                # Never overwrite an existing user-edited graph with a template.
                if item.id not in self.saved and item.id not in self.registered:
                    check_interface(item.graph, self.catalog)
                    from .graph import GraphError, compile_graph
                    try:
                        compile_graph(item.graph, self.catalog, self.root, input_roots=self.input_roots)
                        item.graph = freeze_graph(item.graph, self.catalog_for(item.graph), self.root, input_roots=self.input_roots)
                        saved = SavedWorkflow(id=item.id, version=item.version, graph=item.graph,
                                              updated_at=datetime.now(timezone.utc).isoformat())
                        self._write_saved(saved)
                        self.saved[item.id], self.registered[item.id] = saved, item
                    except GraphError as exc:
                        print(f"Operon: skipping incompatible built-in route {item.id}: {exc}", file=sys.stderr)
                installed.add(item.id)
            self._write(self.directory / "registry.json", [r.model_dump(mode="json") for r in self.registered.values()])
            self._write(receipt, sorted(installed))
            self.changed()

    def save_workspace(self, workspace: Workspace):
        ids = [document.id for document in workspace.documents]
        if len(set(ids)) != len(ids) or workspace.active_id not in ids:
            fail("页面 ID 重复或活动页面不存在。")
        with self.lock:
            self._write(self.directory / "workspace.json", workspace.model_dump(mode="json"))

    def load_workspace(self):
        try:
            value = Workspace.model_validate_json((self.directory / "workspace.json").read_text(encoding="utf-8"))
            return value.model_dump(mode="json")
        except FileNotFoundError:
            return None
        except ValueError as exc:
            fail("Workspace is invalid or uses an older graph protocol. Close Studio and run operon migrate; the file has been preserved. " + str(exc))
