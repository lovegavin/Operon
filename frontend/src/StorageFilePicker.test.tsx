import {isValidElement, type ReactNode} from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError} from './api';
import {StorageFilePicker, storageParent} from './StorageFilePicker';
import type {StorageEntry, StoragePage} from './storageTypes';

type Effect = {deps?: unknown[]; cleanup?: () => void};
const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0, effects: [] as (() => void)[]}));
vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {...actual,
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = typeof initial === 'function' ? initial() : initial;
      return [hooks.values[index], (next: unknown) => {
        hooks.values[index] = typeof next === 'function' ? next(hooks.values[index]) : next;
      }];
    },
    useRef: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values)) hooks.values[index] = {current: initial};
      return hooks.values[index];
    },
    useEffect: (effect: () => void | (() => void), deps?: unknown[]) => {
      const index = hooks.cursor++, previous = hooks.values[index] as Effect | undefined;
      if (previous && deps?.every((value, key) => value === previous.deps?.[key])) return;
      const slot: Effect = {deps}; hooks.values[index] = slot;
      hooks.effects.push(() => {previous?.cleanup?.(); slot.cleanup = effect() || undefined;});
    }};
});
vi.mock('./api', async importOriginal => {
  const actual = await importOriginal<typeof import('./api')>();
  return {...actual, api: {storageRoots: vi.fn(), browseStorage: vi.fn(), closeStorageBrowse: vi.fn(),
    statStorage: vi.fn(), previewStorage: vi.fn()}};
});

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
const onClose = vi.fn(), onSelect = vi.fn();
function render() {hooks.cursor = 0; return StorageFilePicker({onClose, onSelect});}
function find(type: string, label: string) {
  const result = elements(render()).find(value => value.type === type &&
    (value.props['aria-label'] === label || text(value.props.children as ReactNode) === label));
  expect(result, label).toBeDefined(); return result!;
}
function click(label: string) {(find('button', label).props.onClick as () => void)();}
function entry(name: string, patch: Partial<StorageEntry> = {}): StorageEntry {
  return {ref: {storage_id: 'allowed', relative_path: name, version: 'version-1', digest: null},
    name, kind: 'file', size_bytes: 8, modified_ns: 1, is_symlink: false, accessible: true, ...patch};
}
function page(entries: StorageEntry[], cursor: string | null = null): StoragePage {
  return {entries, next_cursor: cursor, listing_revision: 'revision-1', complete: !cursor, order: 'filesystem', scanned: entries.length};
}
async function mount() {
  render(); hooks.effects.splice(0).forEach(effect => effect());
  await vi.waitFor(() => expect(api.browseStorage).toHaveBeenCalledTimes(1));
  await vi.waitFor(() => expect(elements(render()).find(node => node.props.role === 'listbox')?.props['aria-busy']).toBe(false));
}
function unmount() {for (const value of hooks.values) (value as Effect | null)?.cleanup?.();}

beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; hooks.effects = []; vi.clearAllMocks();
  let sequence = 0;
  vi.stubGlobal('crypto', {randomUUID: () => 'session-' + ++sequence});
  vi.stubGlobal('window', {addEventListener: vi.fn(), removeEventListener: vi.fn()});
  vi.mocked(api.storageRoots).mockResolvedValue({roots: [{storage_id: 'allowed', relative_path: '.'}]});
  vi.mocked(api.browseStorage).mockResolvedValue(page([entry('first.txt')], 'cursor-1'));
  vi.mocked(api.closeStorageBrowse).mockResolvedValue({closed: 1});
  vi.mocked(api.statStorage).mockImplementation(async ref => entry(ref.relative_path));
  vi.mocked(api.previewStorage).mockResolvedValue({entry: entry('first.txt'), text: 'preview', bytes_read: 7,
    rows: 1, truncated: true, decoding_errors: false});
});
afterEach(() => {unmount(); vi.unstubAllGlobals();});

describe('authorized bounded storage picker', () => {
  it('does not invent a workspace mount when none is authorized', async () => {
    vi.mocked(api.storageRoots).mockResolvedValueOnce({roots: []});
    render(); hooks.effects.splice(0).forEach(effect => effect());
    await vi.waitFor(() => expect(text(render())).toContain('尚未配置可浏览目录，请联系管理员。'));
    expect(api.browseStorage).not.toHaveBeenCalled();
  });

  it('replaces the visible page and preserves the opaque cursor/session scope', async () => {
    await mount();
    vi.mocked(api.browseStorage).mockResolvedValueOnce(page([entry('second.txt')]));
    click('下一页');
    await vi.waitFor(() => expect(text(render())).toContain('second.txt'));
    expect(text(render())).not.toContain('first.txt');
    expect(api.browseStorage).toHaveBeenLastCalledWith({storage_id: 'allowed', relative_path: '.',
      hidden: false, order: 'filesystem', cursor: 'cursor-1'}, 'session-1', expect.any(AbortSignal));
  });

  it('restarts an expired listing with a different session instead of retrying its cursor', async () => {
    await mount();
    vi.mocked(api.browseStorage).mockRejectedValueOnce(new ApiError('expired', undefined, 409, 'browse_cursor_expired'));
    click('下一页');
    await vi.waitFor(() => expect(text(render())).toContain('目录已变化或浏览已过期，请重新加载。'));
    click('重新加载');
    await vi.waitFor(() => expect(api.browseStorage).toHaveBeenCalledTimes(3));
    expect(api.browseStorage).toHaveBeenLastCalledWith(expect.objectContaining({cursor: null}),
      'session-2', expect.any(AbortSignal));
    expect(api.closeStorageBrowse).toHaveBeenCalledWith('session-1');
  });

  it('keeps traversal inside the selected root and closes handles on navigation and unmount', async () => {
    vi.mocked(api.browseStorage).mockResolvedValueOnce(page([entry('nested', {kind: 'directory'})], 'cursor-1'));
    await mount(); click('nested');
    await vi.waitFor(() => expect(api.browseStorage).toHaveBeenCalledTimes(2));
    expect(api.browseStorage).toHaveBeenLastCalledWith(expect.objectContaining({relative_path: 'nested', cursor: null}),
      'session-2', expect.any(AbortSignal));
    expect(api.closeStorageBrowse).toHaveBeenCalledWith('session-1');
    unmount(); expect(api.closeStorageBrowse).toHaveBeenCalledWith('session-2');
    expect(storageParent('nested/deeper')).toBe('nested'); expect(storageParent('nested')).toBe('.');
  });

  it('validates the exact selected version and returns its reference without a legacy absolute path', async () => {
    await mount(); click('first.txt'); click('选择文件');
    await vi.waitFor(() => expect(onSelect).toHaveBeenCalledExactlyOnceWith(entry('first.txt').ref));
    expect(api.statStorage).toHaveBeenCalledWith(entry('first.txt').ref, 'session-1', expect.any(AbortSignal));
    expect(api.previewStorage).not.toHaveBeenCalled(); expect(onClose).toHaveBeenCalledOnce();
  });

  it('refuses a selected file whose version changed', async () => {
    await mount();
    vi.mocked(api.statStorage).mockRejectedValueOnce(new ApiError('changed selected file', undefined, 409, 'storage_changed'));
    click('first.txt'); click('选择文件');
    await vi.waitFor(() => expect(text(render())).toContain('changed selected file'));
    expect(onSelect).not.toHaveBeenCalled(); expect(api.previewStorage).not.toHaveBeenCalled();
  });

  it('aborts and retires a listing whose response arrives after close', async () => {
    let finish!: (value: StoragePage) => void;
    vi.mocked(api.browseStorage).mockImplementationOnce(() => new Promise(resolve => {finish = resolve;}));
    render(); hooks.effects.splice(0).forEach(effect => effect());
    await vi.waitFor(() => expect(api.browseStorage).toHaveBeenCalledOnce());
    const signal = vi.mocked(api.browseStorage).mock.calls[0][2];
    unmount(); expect(signal?.aborted).toBe(true);
    finish(page([entry('late.txt')], 'late-cursor'));
    await vi.waitFor(() => expect(api.closeStorageBrowse).toHaveBeenCalledWith('session-1'));
    expect(onSelect).not.toHaveBeenCalled();
    expect(text(render())).not.toContain('late.txt');
  });

  it('shows the bounded preview and refuses inaccessible entries', async () => {
    vi.mocked(api.browseStorage).mockResolvedValueOnce(page([entry('first.txt'), entry('escape', {accessible: false, is_symlink: true})]));
    await mount();
    expect(find('button', 'escape').props.disabled).toBe(true);
    click('first.txt'); click('预览');
    await vi.waitFor(() => expect(text(render())).toContain('仅显示文件开头的有限预览。'));
    expect(api.previewStorage).toHaveBeenCalledWith(entry('first.txt').ref, 'session-1', expect.any(AbortSignal));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
