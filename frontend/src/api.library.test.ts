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
