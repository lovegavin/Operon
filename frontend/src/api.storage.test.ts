import {afterEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';

afterEach(() => vi.unstubAllGlobals());
const response = (value: unknown) => ({ok: true, status: 200, json: async () => value});

describe('storage API authentication and scope', () => {
  it('retains Studio authentication and one cursor session through browse and close', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    fetchMock.mockResolvedValueOnce(response({token: 'studio-owner'}));
    vi.stubGlobal('fetch', fetchMock);
    await api.bootstrap();
    const controller = new AbortController();
    const payload = {storage_id: 'authorized', relative_path: 'data', cursor: 'opaque',
      hidden: false, order: 'filesystem' as const};
    await api.browseStorage(payload, 'picker-session', controller.signal);
    const [url, options] = fetchMock.mock.calls[1];
    expect(url).toBe('/api/v1/storage/browse');
    expect(options.headers['X-Studio-Token']).toBe('studio-owner');
    expect(options.headers['X-Operon-Storage-Session']).toBe('picker-session');
    expect(JSON.parse(options.body)).toEqual(payload);
    expect(options.signal).toBe(controller.signal);
    await api.closeStorageBrowse('picker-session');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/storage/browse/close');
    expect(fetchMock.mock.calls[2][1].headers['X-Operon-Storage-Session']).toBe('picker-session');
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({});
  });

  it('sends exact versioned refs to stat and only the supported bounded-preview fields', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({}));
    vi.stubGlobal('fetch', fetchMock);
    const reference = {storage_id: 'authorized', relative_path: 'data/file.txt', version: 'frozen', digest: null};
    await api.statStorage(reference, 'selection');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(reference);
    await api.previewStorage(reference, 'selection');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({storage_id: 'authorized', relative_path: 'data/file.txt'});
    await api.storageRoots();
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/storage/roots');
    expect(fetchMock.mock.calls[2][1].method).toBe('GET');
  });
});
