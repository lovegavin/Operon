import {t} from './i18n';
import type {PlanBinding, PlanCompile, PlanRecord, PlanUiState, RunPlan} from './planTypes';

export const emptyBinding = (): PlanBinding => ({package_root: '.', environment_store: 'environments', environments: {}, storage: {}, inputs: {}});
export const terminalPlan = (state: string) => ['succeeded', 'complete', 'completed', 'failed', 'cancelled', 'canceled', 'rejected'].includes(state);
export function requiredBindings(plan: RunPlan) {
  return {environments: [...new Set(plan.units.map(unit => unit.invocation.environment_ref || ''))],
    storage: [...new Set(plan.storage_bindings.map(item => item.storage_id))],
    inputs: [...new Set(plan.units.flatMap(unit => Object.values(unit.input_bindings).filter(value => value.startsWith('input:')).map(value => value.slice(6))))]};
}
const confined = (value: string) => !!value && !/^[\\/]|:|\0/.test(value) && !value.replaceAll('\\', '/').split('/').includes('..');
export function bindingProblems(plan: RunPlan, binding: PlanBinding): string[] {
  const required = requiredBindings(plan), problems: string[] = [];
  for (const key of ['package_root', 'environment_store'] as const) if (!confined(binding[key])) problems.push(t('请填写工作区内的相对路径：{name}', {name: key}));
  for (const name of required.environments) {
    const env = binding.environments[name];
    if (!name || !env?.generation_id || !/^[A-Za-z0-9_.-]+$/.test(env.generation_id) || !confined(env.executable)) problems.push(t('缺少固定环境：{name}', {name: name || '—'}));
  }
  for (const name of required.storage) if (!confined(binding.storage[name] || '')) problems.push(t('缺少存储映射：{name}', {name}));
  for (const name of required.inputs) {
    const input = binding.inputs[name];
    if (!input || !confined(input.path) || !/^[a-f0-9]{64}$/.test(input.sha256) || !Number.isSafeInteger(input.size_bytes) || input.size_bytes < 0) problems.push(t('输入尚未核对：{name}', {name}));
  }
  return problems;
}
/** Import wrappers are unwrapped, never merged into the active canvas or current defaults. */
export function parsePlanFile(text: string): {plan?: RunPlan; binding?: PlanBinding; compile?: PlanCompile} {
  const value = JSON.parse(text);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(t('请选择执行计划或编译清单 JSON。'));
  const plan = value.format === 'operon.run-plan' ? value : value.plan;
  if (plan) {
    if (plan.format !== 'operon.run-plan' || plan.schema_version !== 1 || typeof plan.plan_id !== 'string' || typeof plan.parameters_digest !== 'string'
      || !Array.isArray(plan.units) || !plan.units.length || !Array.isArray(plan.storage_bindings)
      || plan.units.some((unit: RunPlan['units'][number]) => !unit || typeof unit.unit_id !== 'string' || !unit.invocation || !unit.placement?.target || !unit.resource_request || !unit.input_bindings)
      || plan.storage_bindings.some((item: RunPlan['storage_bindings'][number]) => !item || typeof item.storage_id !== 'string')) throw Error(t('执行计划格式不受支持。'));
    if (value.binding && (!value.binding.environments || !value.binding.inputs || !value.binding.storage)) throw Error(t('执行绑定清单不完整。'));
    return {plan: structuredClone(plan), ...(value.binding ? {binding: structuredClone(value.binding)} : {})};
  }
  if (value.workflow && (value.kind === 'authoring-v2' || value.kind === 'graph' || !value.kind)) return {compile: value};
  if (Array.isArray(value.nodes) && Array.isArray(value.edges)) return {compile: {kind: 'graph', workflow: value}};
  throw Error(t('请选择执行计划或编译清单 JSON。'));
}
export function recordSubmission(plan: RunPlan, binding: PlanBinding, title: string): PlanRecord {
  const problems = bindingProblems(plan, binding);
  if (problems.length) throw Error(problems.join('\n'));
  return {title: title.slice(0, 200) || plan.plan_id, created_at: new Date().toISOString(), status: 'pending',
    submission: structuredClone({plan, binding, request_id: `desktop-${crypto.randomUUID()}`})};
}
export function appendRecord(state: PlanUiState, record: PlanRecord): PlanUiState {
  if (state.records.length >= 20) throw Error(t('计划记录已满，请先归档已确认的记录。未确认的提交不会被移除。'));
  return {...state, records: [record, ...state.records]};
}
/** One request at a time; aborting observation never requests scientific cancellation. */
export function observePlan(work: (signal: AbortSignal) => Promise<boolean>, error: (failure: unknown) => void, delay = 2500) {
  const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
  const tick = async () => {
    try {const again = await work(controller.signal); if (again && !controller.signal.aborted) timer = setTimeout(tick, delay);}
    catch (failure) {if (!controller.signal.aborted) error(failure);}
  };
  void tick();
  return () => {controller.abort(); if (timer !== undefined) clearTimeout(timer);};
}
