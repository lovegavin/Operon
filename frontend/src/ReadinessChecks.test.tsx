import {beforeEach, expect, it, vi} from 'vitest';
import {isValidElement, type ReactNode} from 'react';
import {ReadinessChecks} from './ReadinessChecks';
import {api, type CheckFeedback, type Readiness} from './api';
import type {Graph} from './types';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async original => ({...await original<typeof import('react')>(), useState: (initial: unknown) => {
  const index = hooks.cursor++;
  if (!(index in hooks.values)) hooks.values[index] = initial;
  return [hooks.values[index], (next: unknown) => {hooks.values[index] = next;}];
}}));
vi.mock('./api', () => ({api: {validate: vi.fn(), checkEnvironment: vi.fn(), prepareEnvironment: vi.fn()}}));
const graph: Graph = {schema_version: 2, name: 'Draft', base_dir: '.', memory: {enabled: true}, edges: [],
  nodes: [{id: 'input', kind: 'source', title: 'Input', input_count: 0, position: {x: 0, y: 0}, params: {}, source: {path: '', dims: [], labels: {}, args: {}}}]};
const blocked: Readiness = {status: 'blocked', fingerprint: 'a', checked_at: '',
  blocked: [{target: 'local', id: 'pca', status: 'failed', message: 'Missing numpy'}]};
const ready: Readiness = {...blocked, status: 'ready', blocked: []};
type Element = {type: unknown; props: Record<string, unknown>};
function elements(value: ReactNode): Element[] {
  if (Array.isArray(value)) return value.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(value)) return [];
  return [value, ...elements(value.props.children as ReactNode)];
}
function render(value = graph, preflight?: CheckFeedback) {
  hooks.cursor = 0;
  return elements(ReadinessChecks({graph: value, disabled: false, preflight}));
}
function button(label: string, nodes = render()) {
  return nodes.find(node => node.type === 'button' && (Array.isArray(node.props.children)
    ? node.props.children.includes(label) : node.props.children === label));
}
async function click(label: string) {
  (button(label)!.props.onClick as () => void)();
  await vi.waitFor(() => expect(button('环境依赖检查')!.props.disabled).toBe(false));
}
beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; vi.clearAllMocks();
  vi.mocked(api.checkEnvironment).mockResolvedValue({readiness: blocked});
  vi.mocked(api.prepareEnvironment).mockResolvedValue({readiness: ready});
});
it('checks and explicitly prepares dependencies without a data file or calling preflight', async () => {
  await click('环境依赖检查');
  expect(api.checkEnvironment).toHaveBeenCalledExactlyOnceWith(graph);
  expect(api.validate).not.toHaveBeenCalled();
  expect(api.prepareEnvironment).not.toHaveBeenCalled();
  expect(button('安装当前路线所需依赖')).toBeDefined();
  await click('安装当前路线所需依赖');
  expect(api.prepareEnvironment).toHaveBeenCalledExactlyOnceWith(graph);
  expect(button('安装当前路线所需依赖')).toBeUndefined();
  expect(render().some(node => node.props.children === '运行前检查通过')).toBe(false);
});
it('keeps complete validation errors visible and the dependency check independently usable', async () => {
  vi.mocked(api.validate).mockRejectedValue(new Error('Choose an input file'));
  await click('运行前检查');
  expect(render().some(node => node.props.role === 'alert' && node.props.children === 'Choose an input file')).toBe(true);
  await click('环境依赖检查');
  expect(button('安装当前路线所需依赖')).toBeDefined();
});
it('shows an installation entry for a blocked toolbar check, even after an earlier dependency success', async () => {
  vi.mocked(api.checkEnvironment).mockResolvedValue({readiness: ready});
  await click('环境依赖检查');
  expect(button('安装当前路线所需依赖', render(graph, {signature: JSON.stringify(graph), readiness: blocked}))).toBeDefined();
});
it('does not present an old success or repair result as valid after the graph changes', async () => {
  vi.mocked(api.checkEnvironment).mockResolvedValue({readiness: ready});
  await click('环境依赖检查');
  expect(render().some(node => node.props.children === '依赖已就绪')).toBe(true);
  const changed = {...graph, runtime: {execution: {kind: 'ssh', profile_id: 'new-server'}}};
  expect(render(changed).some(node => node.props.children === '依赖已就绪')).toBe(false);
});
