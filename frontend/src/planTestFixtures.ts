import {emptyBinding} from './planState';
import type {PlanBinding, RunPlan} from './planTypes';
export function samplePlan(): RunPlan {
  return {format: 'operon.run-plan', schema_version: 1, plan_id: 'a'.repeat(64), workflow_revision: 'b'.repeat(64),
    parameters_digest: 'c'.repeat(64), compiler_version: 'test', environment_requirements: [], storage_bindings: [],
    units: [{unit_id: 'scale', node_ids: ['scale'], invocation: {kind: 'command', environment_ref: 'python'},
      input_bindings: {}, output_contracts: [], placement: {executor: 'local', target: {os: 'windows', arch: 'x86_64'}},
      resource_request: {cpu_threads: 1, process_reservation_bytes: 1024}}]};
}
export function sampleBinding(): PlanBinding {return {...emptyBinding(), environments: {python: {generation_id: 'fixed-1', executable: 'python.exe'}}};}
