import {isValidElement, type ReactNode} from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ApiError} from './api';
import {PlanPanel} from './PlanPanel';
import {planApi} from './planApi';
import {sampleBinding, samplePlan} from './planTestFixtures';
import type {PlanUiState} from './planTypes';
import type {Graph} from './types';

type Effect = {deps?: unknown[]; cleanup?: () => void};
const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0, effects: [] as (() => void)[]}));
vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {...actual,
    useState: (initial: unknown) => {const i = hooks.cursor++; if (!(i in hooks.values)) hooks.values[i] = typeof initial === 'function' ? initial() : initial;
      return [hooks.values[i], (next: unknown) => {hooks.values[i] = typeof next === 'function' ? next(hooks.values[i]) : next;}];},
    useRef: (initial: unknown) => {const i = hooks.cursor++; if (!(i in hooks.values)) hooks.values[i] = {current: initial}; return hooks.values[i];},
    useEffect: (effect: () => void | (() => void), deps?: unknown[]) => {const i = hooks.cursor++, old = hooks.values[i] as Effect | undefined;
      if (old && deps?.every((value, key) => value === old.deps?.[key])) return;
      const slot: Effect = {deps}; hooks.values[i] = slot; hooks.effects.push(() => {old?.cleanup?.(); slot.cleanup = effect() || undefined;});},
  };
});
vi.mock('./planApi', () => ({planApi: {state: vi.fn(), saveState: vi.fn(), compile: vi.fn(), bindingOptions: vi.fn(), submit: vi.fn()}}));
type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {if (Array.isArray(node)) return node.flatMap(elements); if (!isValidElement<Record<string, unknown>>(node)) return []; return [node, ...elements(node.props.children as ReactNode)];}
function text(node: ReactNode): string {if (Array.isArray(node)) return node.map(text).join(''); if (isValidElement<Record<string, unknown>>(node)) return text(node.props.children as ReactNode); return typeof node === 'string' || typeof node === 'number' ? String(node) : '';}
let graph: Graph, serverState: PlanUiState;
const onClose = vi.fn();
function render() {hooks.cursor = 0; return PlanPanel({graph, onClose});}
function find(type: string, label: string) {const result = elements(render()).find(item => item.type === type && (item.props['aria-label'] === label || text(item.props.children as ReactNode) === label)); expect(result, label).toBeDefined(); return result!;}
function click(label: string) {(find('button', label).props.onClick as () => void)();}
async function mount() {render(); hooks.effects.splice(0).forEach(effect => effect()); await vi.waitFor(() => expect(planApi.state).toHaveBeenCalled()); await Promise.resolve();}
function unmount() {for (const value of hooks.values) (value as Effect | null)?.cleanup?.();}
async function importBinding() {
  (find('input', '导入绑定清单').props.onChange as (event: unknown) => void)({target: {files: [{text: async () => JSON.stringify(sampleBinding())}], value: 'file'}});
  await vi.waitFor(() => expect(find('button', '提交此计划').props.disabled).toBe(false));
}
beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; hooks.effects = []; vi.clearAllMocks();
  graph = {schema_version: 2, name: 'Frozen test', base_dir: '.', nodes: [], edges: [], memory: {enabled: true}};
  serverState = {version: 1, revision: 0, records: [], exports: []};
  vi.stubGlobal('crypto', {randomUUID: () => 'original-key'});
  vi.mocked(planApi.state).mockImplementation(async () => structuredClone(serverState));
  vi.mocked(planApi.saveState).mockImplementation(async value => {serverState = structuredClone({...value, revision: value.revision + 1}); return structuredClone(serverState);});
  vi.mocked(planApi.compile).mockResolvedValue(samplePlan());
  vi.mocked(planApi.submit).mockResolvedValue({run_id: 'run-accepted', state: 'queued'});
});
afterEach(() => {unmount(); vi.unstubAllGlobals();});

describe('explicit desktop plan lifecycle', () => {
  it('compiles a canvas snapshot without submitting or silently preparing an environment', async () => {
    await mount(); click('编译快照');
    await vi.waitFor(() => expect(planApi.compile).toHaveBeenCalledOnce());
    await vi.waitFor(() => expect(find('button', '提交此计划').props.disabled).toBe(true));
    expect(planApi.submit).not.toHaveBeenCalled(); expect(planApi.bindingOptions).not.toHaveBeenCalled();
    const submitted = vi.mocked(planApi.compile).mock.calls[0][0]; graph.name = 'Later edit';
    expect(submitted.workflow.name).toBe('Frozen test');
  });
  it('persists exact identity before submit and retains it across an unknown response and reopening', async () => {
    await mount(); click('编译快照'); await vi.waitFor(() => expect(text(render())).toContain('执行绑定')); await importBinding();
    vi.mocked(planApi.submit).mockRejectedValueOnce(new ApiError('unknown response', undefined, 503, 'submission_unknown'));
    click('提交此计划');
    await vi.waitFor(() => expect(serverState.records[0]?.status).toBe('unknown'));
    expect(planApi.saveState).toHaveBeenCalledTimes(2);
    expect(vi.mocked(planApi.saveState).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(planApi.submit).mock.invocationCallOrder[0]);
    const original = structuredClone(serverState.records[0].submission);
    unmount(); hooks.values = []; hooks.effects = []; graph.name = 'Other canvas'; await mount();
    click('计划记录1');
    const history = elements(render()).find(item => item.type === 'button' && text(item.props.children as ReactNode).includes('Frozen test'))!;
    (history.props.onClick as () => void)(); click('用原标识确认提交');
    await vi.waitFor(() => expect(serverState.records[0]?.run_id).toBe('run-accepted'));
    expect(vi.mocked(planApi.submit).mock.calls[1][0]).toEqual(original);
  });
  it('refuses to submit when persistent history saving conflicts', async () => {
    await mount(); click('编译快照'); await vi.waitFor(() => expect(text(render())).toContain('执行绑定')); await importBinding();
    vi.mocked(planApi.saveState).mockRejectedValueOnce(new ApiError('Another client changed history', undefined, 409, 'plan_ui_conflict'));
    click('提交此计划'); await vi.waitFor(() => expect(text(render())).toContain('Another client changed history'));
    expect(planApi.submit).not.toHaveBeenCalled();
  });
  it('selects only verified discovered generations and fingerprints only explicitly entered inputs', async () => {
    await mount(); click('编译快照'); await vi.waitFor(() => expect(text(render())).toContain('执行绑定'));
    vi.mocked(planApi.bindingOptions).mockResolvedValue({package_root: '.', environment_store: 'environments', storage: {}, inputs: {},
      environments: {python: [{generation_id: 'verified', executable: 'python.exe', verified: true}, {generation_id: 'unverified', executable: 'fake'}]}});
    click('核对环境与输入'); await vi.waitFor(() => expect(find('button', '提交此计划').props.disabled).toBe(false));
    expect(elements(render()).filter(item => item.type === 'option').map(item => item.props.value)).not.toContain('unverified');
    expect(vi.mocked(planApi.bindingOptions).mock.calls[0][3]).toEqual({});
    expect(planApi.submit).not.toHaveBeenCalled();
  });
});
