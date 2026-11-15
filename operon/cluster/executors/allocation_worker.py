"""Run the existing invocation worker inside an existing Slurm allocation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def allocation_limits(memory_bytes, cpu_threads, *, environ=None, cgroup_root=Path('/sys/fs/cgroup'),
                      proc_cgroup=Path('/proc/self/cgroup')):
    env = os.environ if environ is None else environ
    if not env.get('SLURM_JOB_ID'):
        raise RuntimeError('This worker requires an existing Slurm allocation')
    cpu = min(cpu_threads, int(env['SLURM_CPUS_PER_TASK']))
    if hasattr(os, 'sched_getaffinity'):
        cpu = min(cpu, len(os.sched_getaffinity(0)))
    candidates = [memory_bytes]
    if env.get('SLURM_MEM_PER_NODE'):
        candidates.append(int(env['SLURM_MEM_PER_NODE']) * 1024 * 1024)
    elif env.get('SLURM_MEM_PER_CPU'):
        candidates.append(int(env['SLURM_MEM_PER_CPU']) * 1024 * 1024 * cpu)
    else:
        raise RuntimeError('Allocation memory limit is not reported')
    # Check the actual cgroup v2 membership and each ancestor, including a
    # namespace root. Reading only /sys/fs/cgroup/memory.max can miss a leaf cap.
    roots = [cgroup_root]
    if proc_cgroup.exists():
        for line in proc_cgroup.read_text().splitlines():
            if line.startswith('0::'):
                relative = Path(line[3:].lstrip('/'))
                if '..' in relative.parts:
                    raise RuntimeError('Invalid cgroup membership')
                leaf = cgroup_root / relative
                roots = [leaf, *(parent for parent in leaf.parents if parent.is_relative_to(cgroup_root))]
    for root in roots:
        limit = root / 'memory.max'
        if limit.exists():
            raw = limit.read_text().strip()
            if raw != 'max':
                candidates.append(int(raw))
        quota = root / 'cpu.max'
        if quota.exists():
            maximum, period = quota.read_text().split()
            if maximum != 'max':
                cpu = min(cpu, max(1, int(maximum) // int(period)))
    memory = min(candidates)
    if memory <= 0 or cpu <= 0:
        raise RuntimeError('Allocation budget must be positive')
    return memory, cpu


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invocation', required=True, type=Path)
    parser.add_argument('--memory-bytes', required=True, type=int)
    parser.add_argument('--cpu-threads', required=True, type=int)
    args = parser.parse_args(argv)
    memory, cpu = allocation_limits(args.memory_bytes, args.cpu_threads)
    value = json.loads(args.invocation.read_text(encoding='utf-8'))
    # Immutable input is preserved; an allocation-specific invocation is a sibling
    # so task-relative paths retain their existing meaning.
    value['memory_bytes'] = min(value['memory_bytes'] or memory, memory)
    value['threads'] = min(value['threads'] or cpu, cpu)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = str(value['threads'])
    os.environ['OPERON_SLURM_ALLOCATION'] = os.environ['SLURM_JOB_ID']
    bound = args.invocation.with_name(args.invocation.stem + '.allocation-' + os.environ['SLURM_JOB_ID'] + '.json')
    with bound.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
    from operon.execution.worker_main import main as worker_main
    return worker_main(['--invocation', str(bound)])


if __name__ == '__main__':
    raise SystemExit(main())
