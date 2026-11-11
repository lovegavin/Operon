import {isValidElement, type ReactNode} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {RemoteLibraryPanel} from './RemoteLibraryPanel';
import {api} from './api';
import type {RemoteLibraryCheck} from './types';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0, effects: [] as (() => unknown)[]}));
vi.mock('react', async original => ({...await original<typeof import('react')>(),
  useEffect: (fn: () => unknown) => {hooks.effects.push(fn);},
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return [hooks.values[index], (next: unknown) => {hooks.values[index] = typeof next === 'function' ? next(hooks.values[index]) : next;}];
  },
}));
vi.mock('./api', () => ({api: {checkRemoteLibrary: vi.fn(), installRemoteLibrary: vi.fn(), remoteLibraryStatus: vi.fn()}}));
type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(node)) return [];
  return [node, ...elements(node.props.children as ReactNode)];
}
function text(node: ReactNode): string {
  if (Array.isArray(node)) return node.map(text).join('');
  if (isValidElement<Record<string, unknown>>(node)) return text(node.props.children as ReactNode);
  return typeof node === 'string' || typeof node === 'number' ? String(node) : '';
}
function trigger(element: Element, event: string, value: unknown = {}) {(element.props[event] as (value: unknown) => void)(value);}
const sample: RemoteLibraryCheck = {local_revision: 'local', remote_revision: 'server', supported: true, missing_count: 2,
  changed_count: 1, replacement_required: true,
  packages: ['package-a', 'package-b'].map(name => ({name, version: '1', remote_version: null, missing: [{id: name + '.operator', kind: 'operator'}],
    disabled: [], replaces: 0, selectable: true}))};
const onUpdate = vi.fn(async () => {}), onBusyChange = vi.fn(), onInstall = vi.fn();
let initial: RemoteLibraryCheck | undefined;
function render() {hooks.cursor = 0; hooks.effects = []; return RemoteLibraryPanel({id: 'server', initial, disabled: false, onUpdate, onBusyChange, onInstall});}
function button(label: string) {return elements(render()).find(e => e.type === 'button' && text(e.props.children as ReactNode).startsWith(label))!;}
beforeEach(() => {
  hooks.values = []; hooks.effects = []; hooks.cursor = 0; vi.clearAllMocks(); initial = structuredClone(sample);
  vi.mocked(api.checkRemoteLibrary).mockResolvedValue(sample);
  vi.mocked(api.remoteLibraryStatus).mockResolvedValue({status: 'idle'});
  vi.mocked(api.installRemoteLibrary).mockResolvedValue({status: 'running', phase: 'checking'});
});
describe('server library status', () => {
  it('shows the comparison and offers only a whole-server install', () => {
    const tree = render();
    expect(text(tree)).toContain('服务端缺少 2 个本地算子 / Reader');
    expect(text(tree)).toContain('服务端有 1 个算子实现与本地不一致');
    expect(text(tree)).toContain('安装 / 升级服务端');
    expect(elements(tree).some(e => e.type === 'input')).toBe(false);
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
    trigger(button('安装 / 升级服务端'), 'onClick');
    expect(onInstall).toHaveBeenCalledOnce();
  });
  it('shows legacy-server guidance without starting an installation', () => {
    initial = {...sample, supported: false, packages: []};
    expect(text(render())).toContain('请先安装 / 升级服务端以补齐算子。');
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
    expect(onInstall).not.toHaveBeenCalled();
  });
  it('checks on opening an existing connection only when its handshake has no comparison', async () => {
    initial = undefined; render();
    const cleanup = hooks.effects[2]();
    await vi.waitFor(() => expect(api.checkRemoteLibrary).toHaveBeenCalledExactlyOnceWith('server'));
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
    expect(api.remoteLibraryStatus).not.toHaveBeenCalled();
    (cleanup as () => void)();
  });
  it('surfaces a failed manual recheck without installing', async () => {
    vi.mocked(api.checkRemoteLibrary).mockRejectedValue(new Error('Connection lost'));
    trigger(button('检查算子库'), 'onClick');
    await vi.waitFor(() => expect(text(render())).toContain('Connection lost'));
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
  });
});
