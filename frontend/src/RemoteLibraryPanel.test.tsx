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
  packages: ['package-a', 'package-b'].map(name => ({name, version: '1', remote_version: null, missing: [{id: name + '.operator', kind: 'operator'}],
    disabled: [], replaces: 0, selectable: true}))};
const onUpdate = vi.fn(async () => {}), onBusyChange = vi.fn();
let initial: RemoteLibraryCheck | undefined;
function render() {hooks.cursor = 0; hooks.effects = []; return RemoteLibraryPanel({id: 'server', initial, disabled: false, onUpdate, onBusyChange});}
function button(label: string) {return elements(render()).find(e => e.type === 'button' && text(e.props.children as ReactNode).startsWith(label))!;}
beforeEach(() => {
  hooks.values = []; hooks.effects = []; hooks.cursor = 0; vi.clearAllMocks(); initial = structuredClone(sample);
  vi.mocked(api.checkRemoteLibrary).mockResolvedValue(sample);
  vi.mocked(api.remoteLibraryStatus).mockResolvedValue({status: 'idle'});
  vi.mocked(api.installRemoteLibrary).mockResolvedValue({status: 'running', phase: 'checking'});
});
describe('server library selection', () => {
  it('displays connection results without installing or selecting anything', () => {
    expect(text(render())).toContain('服务端缺少 2 个本地算子 / Reader');
    expect(button('补齐所选算子包').props.disabled).toBe(true);
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
  });
  it('sends only selected providers and both comparison revisions', async () => {
    const checkbox = elements(render()).find(e => e.type === 'input')!;
    trigger(checkbox, 'onChange', {target: {checked: true}});
    trigger(button('补齐所选算子包'), 'onClick');
    await vi.waitFor(() => expect(api.installRemoteLibrary).toHaveBeenCalledExactlyOnceWith('server',
      {packages: ['package-a'], local_revision: 'local', remote_revision: 'server'}));
    expect(button('补齐所选算子包').props.disabled).toBe(true);
  });
  it('prevents disabled/remote-only replacements and discloses package updates', () => {
    initial!.packages![0] = {...initial!.packages![0], selectable: false, reason: 'remote_only_entries', replaces: 7};
    expect(elements(render()).find(e => e.type === 'input')!.props.disabled).toBe(true);
    expect(text(render())).toContain('服务端含本地没有的算子');
    expect(text(render())).toContain('同时更新服务端已有的 7 个算子');
  });
  it('shows legacy-server guidance without starting a server installation', () => {
    initial = {...sample, supported: false, packages: []};
    expect(text(render())).toContain('请先安装 / 升级服务端以补齐算子。');
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
  });
  it('checks on opening an existing connection only when its handshake has no comparison', async () => {
    initial = undefined; render();
    const cleanup = hooks.effects[2]();
    await vi.waitFor(() => expect(api.checkRemoteLibrary).toHaveBeenCalledExactlyOnceWith('server'));
    expect(api.installRemoteLibrary).not.toHaveBeenCalled();
    (cleanup as () => void)();
  });
  it('reuses the automatic connection comparison and recovers a pending operation', async () => {
    vi.mocked(api.remoteLibraryStatus).mockResolvedValue({status: 'running', phase: 'installing'});
    render(); const cleanup = hooks.effects[2]();
    await vi.waitFor(() => expect(api.remoteLibraryStatus).toHaveBeenCalled());
    await Promise.resolve();
    expect(api.checkRemoteLibrary).not.toHaveBeenCalled();
    expect(text(render())).toContain('注册服务端算子');
    (cleanup as () => void)();
  });
  it('manual recheck clears obsolete selections and exposes recoverable errors', async () => {
    trigger(elements(render()).find(e => e.type === 'input')!, 'onChange', {target: {checked: true}});
    vi.mocked(api.checkRemoteLibrary).mockResolvedValue({...sample, packages: [], missing_count: 0});
    trigger(button('检查算子库'), 'onClick');
    await vi.waitFor(() => expect(text(render())).toContain('服务端没有缺少的本地算子'));
    vi.mocked(api.checkRemoteLibrary).mockRejectedValue(new Error('Connection lost'));
    trigger(button('检查算子库'), 'onClick');
    await vi.waitFor(() => expect(text(render())).toContain('Connection lost'));
  });
});
