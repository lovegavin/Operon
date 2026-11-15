"""Slurm command fixtures only; a real site acceptance is a separate K10 gate."""
from dataclasses import replace
import json

import pytest

from operon.cluster.executors.slurm import (CommandResult, SlurmExecutor, SlurmRecord,
    SlurmResources, allocation_script, normalize, parse_records)
from operon.cluster.executors.allocation_worker import allocation_limits
from operon.cluster.receipts import Dispatch


def dispatch(handle=None):
    payload = {'resources': {'account': 'account', 'partition': 'compute', 'cpu_threads': 2,
        'memory_bytes': 200000000, 'wall_seconds': 61}, 'script_path': '/shared/attempt.sh',
        'stdout_path': '/shared/stdout.log', 'stderr_path': '/shared/stderr.log',
        'accounting_start': '2026-11-14T00:00:00'}
    return Dispatch('command', 'attempt', 'run', 'unit', 'slurm1', 'slurm', 'operon-key',
                    'alice', 'controller', 3, json.dumps(payload), external_handle=handle)


class Transport:
    def __init__(self):
        self.calls, self.queue, self.accounting = [], '', ''
        self.submit = CommandResult(0, '42\n', '')
    def run(self, node_id, argv, **kwargs):
        self.calls.append(tuple(argv))
        if '--version' in argv: return CommandResult(0, 'slurm 24.11.0', '')
        if argv[0] == 'scontrol':
            return CommandResult(0, 'AccountingStoreFlags = job_comment\nPrologFlags = (null)\n', '')
        if argv[0] == 'sbatch':
            if isinstance(self.submit, Exception): raise self.submit
            return self.submit
        if argv[0] == 'squeue': return CommandResult(0, self.queue, '')
        if argv[0] == 'sacct': return CommandResult(0, self.accounting, '')
        return CommandResult(0, '', '')


def test_sbatch_uses_saved_token_and_disables_requeue():
    transport = Transport()
    executor = SlurmExecutor(transport)
    executor.probe('slurm1')
    receipt = executor.launch(dispatch())
    assert receipt.external_handle == '42'
    command = transport.calls[-1]
    assert '--parsable' in command and '--no-requeue' in command
    assert '--comment=operon:operon-key' in command and '--time=2' in command


def test_lost_reply_and_empty_accounting_never_resubmit():
    transport = Transport()
    transport.submit = TimeoutError('Reply lost')
    executor = SlurmExecutor(transport)
    executor.probe('slurm1')
    assert executor.launch(dispatch()).phase == 'submission_unknown'
    assert executor.reconcile(dispatch()).phase == 'accounting_delay'
    transport.queue = '42|operon:operon-key|RUNNING\n'
    assert executor.reconcile(dispatch()).external_handle == '42'
    assert sum(command[0] == 'sbatch' and '--parsable' in command for command in transport.calls) == 1


def test_duplicate_token_and_unowned_cancel_remain_unknown():
    transport = Transport()
    transport.queue = '42|operon:operon-key|RUNNING\n43|operon:operon-key|RUNNING\n'
    executor = SlurmExecutor(transport)
    assert executor.reconcile(dispatch()).phase == 'duplicate_token'
    assert executor.cancel(dispatch()).phase == 'cancel_requires_owned_job_id'
    assert executor.cancel(dispatch('99')).state == 'recovery_required'
    assert not any(command[0] == 'scancel' for command in transport.calls)


def test_scheduler_complete_does_not_certify_artifacts():
    transport = Transport()
    transport.accounting = '42|operon:operon-key|COMPLETED|0:0|\n42.batch||COMPLETED|0:0|\n'
    observed = SlurmExecutor(transport).reconcile(dispatch('42'))
    assert observed.state == 'committing' and observed.stop_confirmed
    assert not observed.evidence['artifact_committed']
    assert normalize(SlurmRecord('42', 'token', 'PENDING')) == ('admitted', False)


def test_argument_validation_and_allocation_entrypoint():
    with pytest.raises(ValueError): SlurmResources('account;bad', 'p', 1, 1, 1)
    with pytest.raises(ValueError): SlurmResources('a', 'p', True, 1, 1)
    script = allocation_script(python='/package/python', invocation_path='/shared/invocation.json',
                               memory_bytes=100, cpu_threads=2)
    assert 'operon.cluster.executors.allocation_worker' in script
    assert 'managed_pool' not in script and 'pip install' not in script


def test_worker_clamps_to_allocation_and_nested_cgroup(tmp_path):
    root = tmp_path / 'cgroup'
    leaf = root / 'job'
    leaf.mkdir(parents=True)
    (root / 'memory.max').write_text('max')
    (leaf / 'memory.max').write_text('1048576')
    (leaf / 'cpu.max').write_text('100000 100000')
    membership = tmp_path / 'membership'
    membership.write_text('0::/job\n')
    memory, cpu = allocation_limits(4000000, 8, environ={'SLURM_JOB_ID': '42',
        'SLURM_CPUS_PER_TASK': '4', 'SLURM_MEM_PER_NODE': '2'}, cgroup_root=root, proc_cgroup=membership)
    assert memory == 1048576 and cpu == 1
