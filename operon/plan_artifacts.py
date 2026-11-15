"""Authorized committed-file metadata, bounded preview and explicit local download."""
from contextlib import contextmanager
import codecs
import hashlib
import json
import mimetypes
import re
import os
from pathlib import Path

from .contracts.base import sha256_hex
from .contracts.plan_artifacts import PlanArtifactFilesQuery, PlanArtifactFileQuery, PlanArtifactPreviewQuery
from .contracts.plan_operations import binding_path
from .engine.contracts import EngineError, digest
from .plan_results import _open_owned, _page
from .bytecode import io_path


def _error(message='Committed result file is unavailable', code='plan_artifact_unavailable', status=409):
    return EngineError(message, code=code, status=status)


def _logical(path):
    text = os.fspath(path)
    if os.name == 'nt' and text.startswith('\\\\?\\'):
        text = '\\\\' + text[8:] if text.startswith('\\\\?\\UNC\\') else text[4:]
    return Path(text)


def _stamp(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


@contextmanager
def opened_result(root, descriptor, *, verify=False):
    """Keep the checked handle, including through HTTP response streaming."""
    try:
        relative = Path(binding_path(descriptor['relative_path']))
        with _open_owned(_logical(root), relative) as (fd, before):
            if before.st_size != descriptor['size_bytes']:
                raise _error('Committed result size changed')
            if verify:
                checksum = hashlib.sha256()
                while block := os.read(fd, 1024 * 1024):
                    checksum.update(block)
                if checksum.hexdigest() != descriptor['sha256'] or _stamp(before) != _stamp(os.fstat(fd)):
                    raise _error('Committed result bytes changed', 'corrupt_artifact')
                os.lseek(fd, 0, os.SEEK_SET)
            yield fd, before
    except (OSError, ValueError, KeyError) as exc:
        raise _error() from exc
    except EngineError as exc:
        if exc.code.startswith('plan_log_'):
            raise _error() from exc
        raise


class PlanArtifactReader:
    def __init__(self, store, root, run):
        self.store, self.root, self.run = store, _logical(root), run

    def _artifact(self, artifact_id):
        try:
            return self._artifact_owned(artifact_id)
        except EngineError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise _error('Committed artifact metadata is invalid', 'corrupt_artifact') from exc

    def _artifact_owned(self, artifact_id):
        with self.store.lock:
            rows = self.store.connection.execute(
                'SELECT a.id,u.run_id AS source_run_id,u.local_id,t.id AS source_attempt_id,t.fence,t.state,'
                't.receipt_json,length(a.manifest_json) AS manifest_bytes FROM artifacts a JOIN attempts t ON t.id=a.attempt_id '
                'JOIN units u ON u.id=t.unit_id JOIN runs r ON r.id=u.run_id '
                "WHERE a.id=? AND a.state='committed' AND r.principal=? AND r.workspace_id=? "
                'AND (u.run_id=? OR EXISTS(SELECT 1 FROM unit_reuses x JOIN units consumer ON consumer.id=x.unit_id '
                "WHERE x.artifact_id=a.id AND consumer.run_id=? AND consumer.state='succeeded'))",
                (artifact_id, self.run['principal'], self.run['workspace_id'], self.run['id'], self.run['id'])).fetchall()
            if len(rows) != 1:
                raise _error('Artifact is not committed and owned by this plan', 'plan_artifact_not_found', 404)
            owner = dict(rows[0])
            if owner['manifest_bytes'] > 8 * 1024 * 1024:
                raise _error('Artifact metadata exceeds the browsing allowance', 'artifact_metadata_limit', 413)
            artifact = self.store.artifact(artifact_id)
            lease = self.store.lease(owner['source_attempt_id'])
            receipt = json.loads(owner['receipt_json'])
            if (owner['state'] != 'succeeded' or not lease or lease['state'] != 'released'
                    or receipt.get('artifact_id') != artifact_id or receipt.get('digest') != artifact['digest']
                    or receipt.get('fence') != owner['fence'] or artifact['fence'] != owner['fence']
                    or receipt.get('attempt_id') != owner['source_attempt_id']
                    or receipt.get('run_id') != owner['source_run_id']):
                raise _error('Artifact publication is not final')
            if owner['source_run_id'] != self.run['id'] and not any(
                    row['state'] == 'pinned' and row['owner'] == 'run:' + self.run['id']
                    for row in self.store.references(artifact_id)):
                raise _error('Reused artifact retention is unavailable')
        manifest = artifact['manifest']
        if len(json.dumps(manifest).encode()) > 8 * 1024 * 1024 or digest(manifest) != artifact['digest']:
            raise _error('Artifact manifest identity differs', 'corrupt_artifact')
        entries = manifest.get('files')
        if not isinstance(entries, list) or not 1 <= len(entries) <= 4096:
            raise _error('Artifact file metadata exceeds the browsing allowance', 'artifact_metadata_limit', 413)
        location = _logical(artifact['location'])
        allowed = [self.root / 'invocations/runs' / owner['source_run_id'] / 'attempts' / owner['source_attempt_id'] / 'outputs',
            self.root / 'invocations/runs' / owner['source_run_id'] / 'nodes' / owner['local_id'] / 'attempts' / owner['source_attempt_id'] / 'outputs',
            self.root / 'invocations/artifacts' / artifact_id]
        if location not in allowed:
            raise _error('Artifact location differs from its owned attempt')
        files, seen = [], set()
        for entry in entries:
            name = binding_path(entry['path'])
            if name in seen or name != entry['path'] or len(name) > 2048:
                raise _error('Artifact file names are ambiguous')
            seen.add(name)
            size, checksum = entry.get('size'), entry.get('sha256')
            if type(size) is not int or size < 0 or not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
                raise _error('Artifact file metadata is invalid')
            file_id = sha256_hex({'artifact_id': artifact_id, 'digest': artifact['digest'], 'file': entry})
            files.append({'file_id': file_id, 'name': name, 'size_bytes': size, 'sha256': checksum,
                          'media_type': mimetypes.guess_type(name)[0] or 'application/octet-stream',
                          'relative_path': (location / name).relative_to(self.root).as_posix()})
        return sorted(files, key=lambda item: item['file_id'])

    def files(self, **values):
        query = PlanArtifactFilesQuery.model_validate(values)
        entries = [{**{key: value for key, value in item.items() if key != 'relative_path'},
                    'page_key': item['file_id']} for item in self._artifact(query.artifact_id)
                   if item['file_id'] > query.after]
        return _page(self.run, 'files', entries[:query.limit + 1], after=query.after, limit=query.limit,
                     max_bytes=query.max_bytes, extra={'artifact_id': query.artifact_id})

    def descriptor(self, **values):
        query = PlanArtifactFileQuery.model_validate(values)
        selected = next((item for item in self._artifact(query.artifact_id) if item['file_id'] == query.file_id), None)
        if selected is None:
            raise _error('File is not in this committed artifact', 'plan_artifact_file_not_found', 404)
        return {'run_id': self.run['id'], 'artifact_id': query.artifact_id, **selected}

    def preview(self, **values):
        query = PlanArtifactPreviewQuery.model_validate(values)
        selected = self.descriptor(artifact_id=query.artifact_id, file_id=query.file_id)
        with opened_result(self.root, selected) as (fd, before):
            data = os.read(fd, query.max_bytes)
            if _stamp(before) != _stamp(os.fstat(fd)):
                raise _error('Result changed during preview')
        complete = len(data) == selected['size_bytes']
        verified = complete and hashlib.sha256(data).hexdigest() == selected['sha256']
        if complete and not verified:
            raise _error('Committed result bytes changed', 'corrupt_artifact')
        try:
            content = codecs.getincrementaldecoder('utf-8')().decode(data, final=complete)
            if '\0' in content:
                raise UnicodeError()
            lines = content.splitlines(keepends=True)
            content, kind = ''.join(lines[:query.max_rows]), 'text'
            truncated = not complete or len(lines) > query.max_rows
        except UnicodeError:
            content, kind, truncated = None, 'binary', not complete
        return {**{key: value for key, value in selected.items() if key != 'relative_path'},
                'kind': kind, 'content': content, 'truncated': truncated, 'bytes_read': len(data),
                'digest_verified': verified}


class OpenedPlanResult:
    def __init__(self, root, descriptor):
        self.descriptor = descriptor
        self.context = opened_result(root, descriptor, verify=True)
        self.fd, self.before = self.context.__enter__()
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.context.__exit__(None, None, None)

    def chunks(self):
        try:
            while block := os.read(self.fd, 1024 * 1024):
                if _stamp(self.before) != _stamp(os.fstat(self.fd)):
                    raise _error('Result changed during download')
                yield block
        finally:
            self.close()
