import {afterEach, describe, expect, it, vi} from 'vitest';
import {appendRecord, bindingProblems, emptyBinding, observePlan, parsePlanFile, recordSubmission, requiredBindings} from './planState';
import {sampleBinding, samplePlan} from './planTestFixtures';
afterEach(() => {vi.useRealTimers(); vi.unstubAllGlobals();});
describe('frozen desktop plan operations', () => {
  it('requires each exact environment, storage root and fingerprinted input', () => {
    const plan = samplePlan(); plan.storage_bindings = [{storage_id: 'reads', relative_path: 'input.txt'}];
    plan.units[0].input_bindings = {source: 'input:reads', previous: 'unit:upstream'};
    expect(requiredBindings(plan)).toEqual({environments: ['python'], storage: ['reads'], inputs: ['reads']});
    expect(bindingProblems(plan, emptyBinding())).toHaveLength(3);
    const binding = sampleBinding(); binding.storage.reads = 'data';
    binding.inputs.reads = {path: 'reads.txt', size_bytes: 0, sha256: '1'.repeat(64), representation: 'file', metadata: {}};
    expect(bindingProblems(plan, binding)).toEqual([]);
    binding.inputs.reads.path = '../outside'; expect(bindingProblems(plan, binding)).toHaveLength(1);
    binding.inputs.reads.path = 'reads.txt'; binding.package_root = 'C:\\private';
    expect(bindingProblems(plan, binding)).toHaveLength(1);
  });
  it('freezes values and bindings before mutation without inventing defaults or changing request IDs', () => {
    vi.stubGlobal('crypto', {randomUUID: () => 'unique'});
    const plan = samplePlan(), binding = sampleBinding(); plan.parameters = {scale: 3};
    const record = recordSubmission(plan, binding, 'Workflow');
    plan.parameters = {scale: 8}; binding.environments.python.generation_id = 'newer';
    expect(record.submission.plan.parameters).toEqual({scale: 3});
    expect(record.submission.binding.environments.python.generation_id).toBe('fixed-1');
    expect(record.submission.request_id).toBe('desktop-unique');
    expect(() => recordSubmission(plan, emptyBinding(), 'bad')).toThrow();
  });
  it('keeps imported manifests separate from the canvas and preserves authoring sidecars', () => {
    const request = {kind: 'authoring-v2', workflow: {format: 'operon.workflow'}, parameters: {values: {a: 3}}, inputs: {data: {path: 'file'}}};
    expect(parsePlanFile(JSON.stringify(request)).compile).toEqual(request);
    expect(parsePlanFile(JSON.stringify({plan: samplePlan(), binding: sampleBinding()})).binding).toEqual(sampleBinding());
    expect(() => parsePlanFile('{}')).toThrow();
  });
  it('never silently evicts a pending submission when history is full', () => {
    vi.stubGlobal('crypto', {randomUUID: () => 'unique'});
    const record = recordSubmission(samplePlan(), sampleBinding(), 'run');
    expect(() => appendRecord({version: 1, revision: 1, records: Array.from({length: 20}, () => record), exports: []}, record)).toThrow();
  });
  it('polls sequentially, aborts an in-flight request on unmount and never polls again', async () => {
    vi.useFakeTimers();
    let release: (value: boolean) => void = () => {};
    const work = vi.fn((signal: AbortSignal) => new Promise<boolean>(resolve => {expect(signal.aborted).toBe(false); release = resolve;}));
    const failed = vi.fn(), stop = observePlan(work, failed, 100);
    await vi.advanceTimersByTimeAsync(500); expect(work).toHaveBeenCalledOnce();
    release(true); await Promise.resolve(); await vi.advanceTimersByTimeAsync(100); expect(work).toHaveBeenCalledTimes(2);
    stop(); expect(work.mock.calls[1][0].aborted).toBe(true);
    release(true); await vi.advanceTimersByTimeAsync(1000); expect(work).toHaveBeenCalledTimes(2); expect(failed).not.toHaveBeenCalled();
  });
});
