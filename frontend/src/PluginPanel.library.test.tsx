import {isValidElement, type ReactNode} from 'react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {PluginPanel} from './PluginPanel';
import {AddOperators} from './AddOperators';
import {LegacyLibraryAlert, LibrarySetupGuide} from './LibraryNotices';
import {ApiError, api} from './api';
import type {LibraryList, PluginState} from './types';

// PluginPanel drives an async operation through hooks; run it with deterministic
// hook slots so a file selection can be followed to completion without a DOM.
const hooks = vi.hoisted(() => ({values: [] as unknown[], refs: [] as {current: unknown}[], cursor: 0}));
vi.mock('react', async original => ({
  ...await original<typeof import('react')>(),
  useEffect: () => {},
  useRef: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.refs)) hooks.refs[index] = {current: initial};
    return hooks.refs[index];
  },
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return [hooks.values[index], (next: unknown) => {
      hooks.values[index] = typeof next === 'function' ? (next as (value: unknown) => unknown)(hooks.values[index]) : next;
    }];
  },
}));
vi.mock('./i18n', async original => ({...await original<typeof import('./i18n')>(), useLocale: () => 'zh-CN' as const}));
vi.mock('./api', async original => {
  const actual = await original<typeof import('./api')>();
  return {...actual, api: {...actual.api, installPlugin: vi.fn(), installLibrary: vi.fn(), libraries: vi.fn(),
    deleteLibrary: vi.fn(), plugins: vi.fn(), pluginOperation: vi.fn()}};
});

type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(node)) return [];
  return [node, ...elements(node.props.children as ReactNode)];
}
function render(onChanged = vi.fn(async () => {})) {
  hooks.cursor = 0;
  return PluginPanel({onClose: () => {}, onChanged, initialTab: 'manage'});
}
function choose(name: string) {
  const field = elements(render()).find(item => item.type === 'input' && item.props.type === 'file')!;
  (field.props.onChange as (event: unknown) => void)({target: {files: [{name}]}});
}

const legacyMessage = 'This library bundle uses the legacy 8.x format.\n'
  + 'Install an operon-library-v0.0.x bundle built for Operon 5.0.0.';
const libraryState: PluginState = {
  generation: '1',
  packages: [{name: 'operon-core', version: '0.0.0', sha256: 'a'}],
  descriptors: [
    {id: 'pca', kind: 'operator', title: 'PCA', distribution: 'operon-core'},
    {id: 'table', kind: 'reader', title: 'Table', distribution: 'operon-core'},
  ],
  library_release: {version: '0.0.0', sha256: 'b'},
};
const libraryList: LibraryList = {count: 2, libraries: [
  {name: 'operon-main', library_version: '0.0.0', sha256: 'a', installed_at: '2026-11-13T12:00:00Z', packages: 1, descriptors: 2, operators: 1, readers: 1},
  {name: 'fork-v0.0.0', library_version: '0.1.0', sha256: 'b', installed_at: '2026-11-13T13:00:00Z', packages: 2, descriptors: 34, operators: 30, readers: 4},
]};

beforeEach(() => {
  hooks.values = [];
  hooks.refs = [];
  hooks.cursor = 0;
  vi.clearAllMocks();
  vi.mocked(api.plugins).mockResolvedValue(libraryState);
  vi.mocked(api.libraries).mockResolvedValue(libraryList);
});

afterEach(() => {vi.unstubAllGlobals();});

it('shows the legacy 8.x message verbatim instead of a generic failure', async () => {
  vi.mocked(api.installLibrary).mockRejectedValue(new ApiError(legacyMessage, undefined, 400));
  choose('operon-library-v8.0.9.zip');
  await vi.waitFor(() => expect(hooks.values).toContain(legacyMessage));
  const tree = elements(render());
  expect(tree.find(item => item.type === LegacyLibraryAlert)?.props.message).toBe(legacyMessage);
  expect(tree.some(item => item.props.className === 'modal-error')).toBe(false);
  expect(api.plugins).not.toHaveBeenCalled();
});

it('reports the library version and counts returned by the install operation', async () => {
  vi.mocked(api.installLibrary).mockResolvedValue({
    library_version: '0.0.0', packages: 12, descriptors: 34, installed: true, idempotent: false,
  });
  choose('operon-library-v0.0.0.operon-library.zip');
  const message = '已导入算子库 v0.0.0：34 个算子 / Reader。';
  await vi.waitFor(() => expect(hooks.values).toContain(message));
  expect(api.installLibrary).toHaveBeenCalledWith(
    expect.objectContaining({name: 'operon-library-v0.0.0.operon-library.zip'}));
});

it('offers the two bundle files when no operator library is installed', () => {
  const tree = elements(render());
  expect(tree.some(item => item.type === LibrarySetupGuide)).toBe(true);
});

it('lists every installed library with counts, package count and a delete button', () => {
  hooks.values[1] = libraryState;
  hooks.values[6] = libraryList;
  const tree = elements(render());
  const rows = tree.filter(item => String(item.props.className || '').split(' ').includes('library-record'));
  expect(rows).toHaveLength(2);
  const text = tree
    .map(item => typeof item.props.children === 'string' ? item.props.children : '')
    .join('|');
  expect(text).toContain('operon-main');
  expect(text).toContain('fork-v0.0.0');
  expect(text).toContain('30 个算子 · 4 个 Reader');
  expect(text).toContain('2 个包');
  expect(text).toContain('导入时间：2026-11-13T13:00:00Z');
  expect(text).not.toContain('当前使用');
  expect(tree.filter(item => item.type === 'button' && item.props.children === '使用此库')).toHaveLength(0);
  expect(tree.filter(item => item.type === 'button' && item.props.children === '删除算子库')).toHaveLength(2);
});

it('shows structured conflicts from a rejected install instead of a bare status', async () => {
  const conflict = '算子库包含冲突：operator pca（fork-v0.0.0）';
  vi.mocked(api.installLibrary).mockRejectedValue(new ApiError(conflict, undefined, 409));
  choose('operon-library-v0.0.0.operon-library.zip');
  await vi.waitFor(() => expect(hooks.values).toContain(conflict));
  const tree = elements(render());
  expect(tree.find(item => item.props.role === 'alert')?.props.children).toBe(conflict);
});

it('asks before deleting and stops when the confirmation is declined', () => {
  hooks.values[1] = libraryState;
  hooks.values[6] = libraryList;
  const confirm = vi.fn(() => false);
  vi.stubGlobal('window', {confirm});
  const controls = elements(render()).filter(item => item.type === 'button' && item.props.children === '删除算子库');
  (controls[1].props.onClick as () => void)();
  expect(confirm).toHaveBeenCalledWith('确定删除算子库 fork-v0.0.0？此操作不可撤销。');
  expect(api.deleteLibrary).not.toHaveBeenCalled();
});

it('deletes a non-active library after confirmation and notifies the parent', async () => {
  hooks.values[1] = libraryState;
  hooks.values[6] = libraryList;
  vi.stubGlobal('window', {confirm: vi.fn(() => true)});
  const onChanged = vi.fn(async () => {});
  vi.mocked(api.deleteLibrary).mockResolvedValue({removed: 'fork-v0.0.0'});
  const controls = elements(render(onChanged)).filter(item => item.type === 'button' && item.props.children === '删除算子库');
  (controls[1].props.onClick as () => void)();
  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled());
  expect(api.deleteLibrary).toHaveBeenCalledWith('fork-v0.0.0');
  expect(hooks.values).toContain('已删除算子库 fork-v0.0.0。');
});

it('shows the server reason when a library is still referenced', async () => {
  hooks.values[1] = libraryState;
  hooks.values[6] = libraryList;
  vi.stubGlobal('window', {confirm: vi.fn(() => true)});
  vi.mocked(api.deleteLibrary).mockRejectedValue(new ApiError('算子库仍被路线或任务引用，无法删除。', undefined, 409));
  const controls = elements(render()).filter(item => item.type === 'button' && item.props.children === '删除算子库');
  (controls[1].props.onClick as () => void)();
  await vi.waitFor(() => expect(hooks.values).toContain('算子库仍被路线或任务引用，无法删除。'));
});
