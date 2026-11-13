import {afterEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError} from './api';
import {setLanguage} from './i18n';

const LEGACY = 'This library bundle uses the legacy 8.x format.\nInstall an operon-library-v0.0.x bundle built for Operon 5.0.0.';
const response = (status: number, value: unknown) => ({ok: status >= 200 && status < 300, status, json: async () => value});

afterEach(() => {vi.unstubAllGlobals(); setLanguage('system');});

async function catchRejection(run: () => Promise<unknown>) {
  try {await run();} catch (error) {return error as ApiError;}
  throw Error('expected the call to reject');
}

describe('POST /api/plugins/install', () => {
  it('keeps the legacy 8.x detail and the 400 status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(400, {detail: LEGACY}));
    vi.stubGlobal('fetch', fetchMock);
    const failure = await catchRejection(() => api.installPlugin(new File(['zip'], 'operon-library-v8.0.9.zip')));
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.message).toBe(LEGACY);
    expect(failure.status).toBe(400);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/plugins/install?filename=operon-library-v8.0.9.zip');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/octet-stream');
  });

  it('returns the async operation that carries library counts', async () => {
    const operation = {id: 'op-1', status: 'running', error: null, result: {library_version: '0.0.0', packages: 12, descriptors: 30, installed: true}};
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(200, operation)));
    await expect(api.installPlugin(new File(['zip'], 'operon-library-v0.0.0.operon-library.zip'))).resolves.toEqual(operation);
  });

  it('surfaces the collection-style detail list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(400, {detail: [{msg: 'bad header'}, {msg: 'bad member'}]})));
    const failure = await catchRejection(() => api.installPlugin(new File(['zip'], 'operon-library-v0.0.0.operon-library.zip')));
    expect(failure.message).toBe('bad header；bad member');
  });
});

describe('POST /api/routes/import-collection', () => {
  it('posts multipart field `file` and returns count plus names', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, {
      count: 2, routes: [{key: 'alpha', name: 'Alpha route'}, {key: 'beta', name: 'Beta route'}],
    }));
    vi.stubGlobal('fetch', fetchMock);
    const file = new File([new Uint8Array([0x50, 0x4b])], 'operon-routes-v0.0.0.zip', {type: 'application/zip'});
    await expect(api.importRouteCollection(file)).resolves.toEqual({
      count: 2, names: ['Alpha route', 'Beta route'], failed: [],
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/routes/import-collection');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    const sent = (init.body as FormData).get('file') as File;
    expect(sent.name).toBe('operon-routes-v0.0.0.zip');
  });

  it('surfaces a pin mismatch detail verbatim with status 400', async () => {
    const detail = 'Route "Alpha" pins operon.scale at code_sha 11111111, but installed package operon-scale 1.2.0 has code_sha 22222222.';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(400, {detail})));
    const failure = await catchRejection(() => api.importRouteCollection(new File(['zip'], 'operon-routes-v0.0.0.zip')));
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.message).toBe(detail);
    expect(failure.status).toBe(400);
  });

  it('accepts the all-or-nothing response without a routes array', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(200, {count: 3})));
    await expect(api.importRouteCollection(new File(['zip'], 'operon-routes-v0.0.0.zip')))
      .resolves.toEqual({count: 3, names: [], failed: []});
  });
});

describe('operator libraries 5.1.0', () => {
  it('reads the installed library list', async () => {
    const list = {count: 1, libraries: [
      {name: 'operon-main', library_version: '0.0.0', sha256: 'a', installed_at: '2026-11-13T12:00:00Z', packages: 1, descriptors: 2, operators: 1, readers: 1},
    ]};
    const fetchMock = vi.fn().mockResolvedValue(response(200, list));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api.libraries()).resolves.toEqual(list);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/libraries');
    expect(init.method).toBe('GET');
  });

  it('posts multipart fields `file` and `name` for a labelled install', async () => {
    const result = {library_version: '0.0.0', packages: 2, descriptors: 34, installed: true};
    const fetchMock = vi.fn().mockResolvedValue(response(200, result));
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['zip'], 'operon-library-v0.0.0.operon-library.zip');
    await expect(api.installLibrary(file, 'fork-v0.0.0')).resolves.toEqual(result);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/libraries/install');
    expect(init.method).toBe('POST');
    const body = init.body as FormData;
    expect((body.get('file') as File).name).toBe('operon-library-v0.0.0.operon-library.zip');
    expect(body.get('name')).toBe('fork-v0.0.0');
  });

  it('omits a blank library name so the backend default applies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, {library_version: '0.0.0', packages: 1, descriptors: 1, installed: true}));
    vi.stubGlobal('fetch', fetchMock);
    await api.installLibrary(new File(['zip'], 'operon-library-v0.0.0.operon-library.zip'), '   ');
    expect((fetchMock.mock.calls[0][1].body as FormData).get('name')).toBeNull();
  });

  it('keeps the server detail and status when an install is rejected', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(400, {detail: 'bad bundle'})));
    const failure = await catchRejection(() => api.installLibrary(new File(['zip'], 'bad.zip')));
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure.message).toBe('bad bundle');
    expect(failure.status).toBe(400);
  });

  it('deletes a library by encoded name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, {removed: 'fork v0'}));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api.deleteLibrary('fork v0')).resolves.toEqual({removed: 'fork v0'});
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/libraries/fork%20v0');
    expect(init.method).toBe('DELETE');
  });

  it('turns a conflict response into a readable detail list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(409, {error: {
      code: 'library_conflict', message: 'conflicts',
      conflicts: [{kind: 'operator', id: 'pca', library: 'fork-v0.0.0'}, {kind: 'reader', id: 'table', library: 'fork-v0.0.0'}],
    }})));
    const failure = await catchRejection(() => api.installLibrary(new File(['zip'], 'fork.zip'), 'fork-v0.0.0'));
    expect(failure.message).toBe('算子库包含冲突：operator pca（fork-v0.0.0）、reader table（fork-v0.0.0）');
    expect(failure.status).toBe(409);
  });

  it('explains a delete blocked by route or task references', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(409, {error: {code: 'library_in_use', message: 'in use'}})));
    const failure = await catchRejection(() => api.deleteLibrary('operon-main'));
    expect(failure.message).toBe('算子库仍被路线或任务引用，无法删除。');
    expect(failure.status).toBe(409);
  });
});

