"""Slurm CLI adapter with durable tokens and conservative lost-reply recovery."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import PurePosixPath
import re
import shlex
import time
import uuid

from ..receipts import ClusterError, Observation

_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
_JOB = re.compile(r'^[1-9][0-9]*(?:_[0-9]+)?$')


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class SSHCommandTransport:
    """Lease existing authenticated Paramiko transport; bounded output/channels."""

    def __init__(self, lease, *, max_output_bytes=1024 * 1024):
        if type(max_output_bytes) is not int or max_output_bytes <= 0:
            raise ValueError('Output bound must be positive')
        self.lease, self.max_output_bytes = lease, max_output_bytes

    def run(self, node_id, argv, *, timeout=30, lifecycle=False):
        if not argv or any(not isinstance(v, str) or '\x00' in v for v in argv):
            raise ValueError('Expected literal argument vector')
        with self.lease(node_id, 'lifecycle' if lifecycle else 'control') as connection:
            client = getattr(connection, 'client', connection)
            channel = client.get_transport().open_session(timeout=min(timeout, 10))
            chunks, errors, size = [], [], 0
            deadline = time.monotonic() + timeout
            try:
                channel.settimeout(min(timeout, 10))
                channel.exec_command(shlex.join(argv))
                while True:
                    progressed = False
                    for ready, receive, destination in ((channel.recv_ready, channel.recv, chunks),
                                                        (channel.recv_stderr_ready, channel.recv_stderr, errors)):
                        if ready():
                            data = receive(65536)
                            size += len(data)
                            if size > self.max_output_bytes:
                                raise ClusterError('Slurm response exceeds configured bound', code='remote_output_limit')
                            destination.append(data)
                            progressed = True
                    if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                        return CommandResult(channel.recv_exit_status(), b''.join(chunks).decode('utf-8', 'replace'),
                                             b''.join(errors).decode('utf-8', 'replace'))
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Slurm command outcome is unknown after timeout')
                    if not progressed:
                        time.sleep(.02)
            finally:
                channel.close()

    def write_script(self, node_id, path, content):
        _absolute(path)
        if len(content.encode()) > 1024 * 1024:
            raise ValueError('Attempt script exceeds 1 MiB')
        with self.lease(node_id, 'control') as connection:
            client = getattr(connection, 'client', connection)
            with client.open_sftp() as sftp:
                temporary = path + '.tmp-' + uuid.uuid4().hex
                try:
                    with sftp.file(temporary, 'wx') as stream:
                        stream.write(content.encode('utf-8'))
                        stream.flush()
                    sftp.chmod(temporary, 0o700)
                    # A unique attempt script is immutable; never overwrite another attempt.
                    sftp.rename(temporary, path)
                except BaseException:
                    try:
                        sftp.remove(temporary)
                    except OSError:
                        pass
                    raise


def _absolute(value):
    if not isinstance(value, str) or not PurePosixPath(value).is_absolute() or '\x00' in value or '\n' in value or '..' in PurePosixPath(value).parts:
        raise ValueError('A validated absolute shared-storage path is required')
    return value


@dataclass(frozen=True)
class SlurmResources:
    account: str
    partition: str
    cpu_threads: int
    memory_bytes: int
    wall_seconds: int
    devices: tuple[str, ...] = ()

    def __post_init__(self):
        if not _NAME.fullmatch(self.account) or not _NAME.fullmatch(self.partition):
            raise ValueError('Slurm account and partition must be validated names')
        if any(type(v) is not int or v <= 0 for v in (self.cpu_threads, self.memory_bytes, self.wall_seconds)):
            raise ValueError('Slurm resources must be positive integers')
        # Site-specific typed GPU mappings require a later explicit capability.
        if self.devices:
            raise ValueError('Slurm devices require a verified site resource mapping')


@dataclass(frozen=True)
class SlurmRecord:
    job_id: str
    token: str
    state: str
    exit_code: str = ''


def parse_records(output, *, accounting=False):
    records = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = line.rstrip('|').split('|')
        if len(fields) != (4 if accounting else 3):
            raise ClusterError('Unrecognized Slurm record format', code='slurm_parse_error')
        job, token, state = (field.strip() for field in fields[:3])
        # Allocation step rows (.batch/.extern) are not independent jobs.
        if '.' in job:
            continue
        if not _JOB.fullmatch(job):
            raise ClusterError('Unexpected Slurm job ID', code='slurm_parse_error')
        records.append(SlurmRecord(job, token, state.split()[0].rstrip('+'), fields[3] if accounting else ''))
    return tuple(records)


def normalize(record: SlurmRecord):
    state = record.state.upper()
    if state in ('PENDING', 'CONFIGURING', 'RESV_DEL_HOLD', 'REQUEUED', 'REQUEUE_HOLD'):
        return 'admitted', False
    if state in ('RUNNING', 'SUSPENDED'):
        return 'running', False
    if state in ('COMPLETING', 'STAGE_OUT'):
        return 'committing', False
    if state == 'COMPLETED':
        return 'committing', True  # Artifact collection/verification still required.
    if state == 'CANCELLED':
        return 'cancelled', True
    if state in ('FAILED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY', 'BOOT_FAIL', 'DEADLINE', 'PREEMPTED', 'REVOKED'):
        return 'failed', True
    return 'recovery_required', False


class SlurmExecutor:
    capability = 'slurm.cli.v1'
    resizable = False
    poll_interval = 10.0

    def __init__(self, transport):
        self.transport = transport
        self._probed = set()

    def probe(self, node_id):
        for command in ('sbatch', 'squeue', 'sacct', 'scancel', 'scontrol'):
            result = self.transport.run(node_id, [command, '--version'])
            if result.returncode != 0 or 'slurm' not in result.stdout.lower():
                raise ClusterError('Required Slurm CLI is unavailable', code='capability_unavailable', details={'command': command})
        configuration = self.transport.run(node_id, ['scontrol', 'show', 'config'], lifecycle=True)
        values = {}
        for line in configuration.stdout.splitlines():
            key, separator, value = line.partition('=')
            if separator:
                values[key.strip()] = value.strip()
        flags = values.get('AccountingStoreFlags', '').lower().split(',')
        if configuration.returncode or 'job_comment' not in flags or 'PrologFlags' not in values:
            raise ClusterError('Durable job comments and site requeue policy must be inspectable', code='slurm_site_capability_unavailable')
        if 'forcerequeueonfail' in values['PrologFlags'].lower():
            raise ClusterError('Site forces requeue despite --no-requeue', code='slurm_uncontrolled_requeue')
        result = self.transport.run(node_id, ['sacct', '--noheader', '--parsable2', '--starttime=now-1minutes',
                                              '--format=JobIDRaw,Comment%160,State,ExitCode'], lifecycle=True)
        if result.returncode:
            raise ClusterError('Slurm accounting access is required', code='slurm_accounting_unavailable')
        parse_records(result.stdout, accounting=True)
        self._probed.add(node_id)
        return {'capability': self.capability, 'accounting': True, 'automatic_requeue': False}

    @staticmethod
    def _token(dispatch):
        if not _NAME.fullmatch(dispatch.request_key):
            raise ValueError('Invalid durable Slurm submission token')
        return 'operon:' + dispatch.request_key

    def launch(self, dispatch):
        if dispatch.node_id not in self._probed:
            raise ClusterError('Probe Slurm capabilities before dispatch', code='capability_unavailable')
        payload = dispatch.payload
        resources = SlurmResources(**payload['resources'])
        script = _absolute(payload['script_path'])
        _absolute(payload['stdout_path'])
        _absolute(payload['stderr_path'])
        token = self._token(dispatch)
        argv = ['sbatch', '--parsable', '--no-requeue', '--job-name=' + dispatch.request_key,
                '--comment=' + token, '--account=' + resources.account, '--partition=' + resources.partition,
                '--cpus-per-task=' + str(resources.cpu_threads),
                '--mem=' + str((resources.memory_bytes + 1048575) // 1048576) + 'M',
                '--time=' + str((resources.wall_seconds + 59) // 60),
                '--output=' + payload['stdout_path'], '--error=' + payload['stderr_path'], script]
        try:
            result = self.transport.run(dispatch.node_id, argv)
            # Even a nonzero CLI exit cannot prove no scheduler-side acceptance.
            if result.returncode:
                return Observation('recovery_required', 'submission_unknown', evidence_json=json.dumps({'token': token, 'returncode': result.returncode}))
            handle = result.stdout.strip()
            if not re.fullmatch(r'[1-9][0-9]*(?:;[A-Za-z0-9_.-]+)?', handle):
                raise ValueError('Malformed sbatch receipt')
            job_id, _, cluster = handle.partition(';')
            if cluster and cluster != payload.get('slurm_cluster'):
                raise ValueError('Unverified Slurm cluster identity')
            return Observation('admitted', 'pending', job_id, evidence_json=json.dumps({'token': token, 'sbatch_receipt': handle}))
        except Exception as exc:
            return Observation('recovery_required', 'submission_unknown', evidence_json=json.dumps({'token': token, 'error': type(exc).__name__}))

    def _records(self, dispatch):
        payload = dispatch.payload
        # Persist this timestamp with dispatch so delayed recovery searches the same window.
        start = payload['accounting_start']
        datetime.fromisoformat(start)
        if not re.fullmatch(r'[0-9T:+.-]+', start):
            raise ValueError('Invalid accounting start time')
        queue = self.transport.run(dispatch.node_id, ['squeue', '--noheader', '--name=' + dispatch.request_key,
                                                      '--format=%i|%k|%T'], lifecycle=True)
        if queue.returncode:
            raise ClusterError('Slurm queue unavailable', code='slurm_queue_unavailable')
        active = tuple(record for record in parse_records(queue.stdout) if record.token == self._token(dispatch))
        if dispatch.external_handle and any(record.job_id == dispatch.external_handle for record in active):
            return active
        accounting = self.transport.run(dispatch.node_id, ['sacct', '--noheader', '--parsable2',
            '--name=' + dispatch.request_key, '--starttime=' + start,
            '--format=JobIDRaw,Comment%160,State,ExitCode'], lifecycle=True)
        if queue.returncode or accounting.returncode:
            raise ClusterError('Slurm queue/accounting unavailable', code='slurm_accounting_unavailable')
        # Active data wins over an older accounting observation for the same job.
        records = {record.job_id: record for record in parse_records(accounting.stdout, accounting=True)}
        records.update({record.job_id: record for record in active})
        return tuple(record for record in records.values() if record.token == self._token(dispatch))

    def reconcile(self, dispatch):
        try:
            records = self._records(dispatch)
            if len(records) != 1:
                return Observation('recovery_required', 'accounting_delay' if not records else 'duplicate_token',
                                   dispatch.external_handle, evidence_json=json.dumps({'matching_jobs': len(records)}))
            record = records[0]
            if dispatch.external_handle and dispatch.external_handle != record.job_id:
                return Observation('recovery_required', 'ownership_mismatch', dispatch.external_handle)
            state, stopped = normalize(record)
            evidence = {'job_id': record.job_id, 'token': record.token, 'slurm_state': record.state,
                        'exit_code': record.exit_code, 'tree_exited': stopped,
                        'compute_complete': record.state == 'COMPLETED', 'artifact_committed': False}
            return Observation(state, 'awaiting_artifacts' if record.state == 'COMPLETED' else record.state.lower(),
                               record.job_id, evidence_json=json.dumps(evidence), stop_confirmed=stopped)
        except Exception as exc:
            return Observation('recovery_required', 'accounting_unavailable', dispatch.external_handle,
                               evidence_json=json.dumps({'error': type(exc).__name__}))

    def poll(self, dispatch):
        return self.reconcile(dispatch)

    def cancel(self, dispatch, *, timeout=10.0):
        if not dispatch.external_handle or not _JOB.fullmatch(dispatch.external_handle):
            return Observation('recovery_required', 'cancel_requires_owned_job_id')
        observed = self.reconcile(dispatch)
        if observed.external_handle != dispatch.external_handle or observed.state == 'recovery_required':
            return observed
        if observed.stop_confirmed:
            return observed
        try:
            result = self.transport.run(dispatch.node_id, ['scancel', '--', dispatch.external_handle],
                                        timeout=timeout, lifecycle=True)
            if result.returncode:
                return Observation('recovery_required', 'cancellation_unconfirmed', dispatch.external_handle)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                observed = self.reconcile(dispatch)
                if observed.stop_confirmed:
                    return observed
                time.sleep(min(.25, max(0, deadline - time.monotonic())))
            return Observation('recovery_required', 'cancellation_unconfirmed', dispatch.external_handle)
        except Exception as exc:
            return Observation('recovery_required', 'cancellation_unconfirmed', dispatch.external_handle,
                               evidence_json=json.dumps({'error': type(exc).__name__}))


def allocation_script(*, python, invocation_path, memory_bytes, cpu_threads):
    """Direct worker within Slurm; no managed host pool or package installer."""
    _absolute(python)
    _absolute(invocation_path)
    if type(memory_bytes) is not int or type(cpu_threads) is not int or min(memory_bytes, cpu_threads) <= 0:
        raise ValueError('Allocation budgets must be positive integers')
    argv = [python, '-m', 'operon.cluster.executors.allocation_worker', '--invocation', invocation_path,
            '--memory-bytes', str(memory_bytes), '--cpu-threads', str(cpu_threads)]
    return '#!/bin/sh\nset -eu\nexec ' + shlex.join(argv) + '\n'
