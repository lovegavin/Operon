import {isValidElement, type ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
import {PluginPanel} from './PluginPanel';
import {LegacyLibraryAlert, LibrarySetupGuide} from './LibraryNotices';
import {ApiError, api} from './api';
import type {PluginState} from './types';

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
  return {...actual, api: {...actual.api, installPlugin: vi.fn(), plugins: vi.fn(), pluginOperation: vi.fn()}};
});

type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(node)) return [];
  return [node, ...elements(node.props.children as ReactNode)];
}
function render() {
  hooks.cursor = 0;
  return PluginPanel({onClose: () => {}, onChanged: vi.fn(async () => {}), initialTab: 'manage'});
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

beforeEach(() => {
  hooks.values = [];
  hooks.refs = [];
  hooks.cursor = 0;
  vi.clearAllMocks();
  vi.mocked(api.plugins).mockResolvedValue(libraryState);
});

it('shows the legacy 8.x message verbatim instead of a generic failure', async () => {
  vi.mocked(api.installPlugin).mockRejectedValue(new ApiError(legacyMessage, undefined, 400));
  choose('operon-library-v8.0.9.zip');
  await vi.waitFor(() => expect(hooks.values).toContain(legacyMessage));
  const tree = elements(render());
  expect(tree.find(item => item.type === LegacyLibraryAlert)?.props.message).toBe(legacyMessage);
  expect(tree.some(item => item.props.className === 'modal-error')).toBe(false);
  expect(api.plugins).not.toHaveBeenCalled();
});

it('reports the library version and counts returned by the install operation', async () => {
  vi.mocked(api.installPlugin).mockResolvedValue({
    id: 'one', status: 'complete', error: null,
    result: {library_version: '0.0.0', packages: 12, descriptors: 34, installed: true, idempotent: false},
  });
  choose('operon-library-v0.0.0.zip');
  const message = '已导入算子库 v0.0.0：12 个包，34 个算子 / Reader。';
  await vi.waitFor(() => expect(hooks.values).toContain(message));
  expect(api.installPlugin).toHaveBeenCalledWith({name: 'operon-library-v0.0.0.zip'});
});

it('offers the two bundle files when no operator library is installed', () => {
  const tree = elements(render());
  expect(tree.some(item => item.type === LibrarySetupGuide)).toBe(true);
});
