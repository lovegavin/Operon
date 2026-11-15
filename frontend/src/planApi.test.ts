import {afterEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';
import {planApi} from './planApi';
import {sampleBinding, samplePlan} from './planTestFixtures';
const response = (value: unknown, status = 200) => ({ok: status < 400, status, json: async () => value});
afterEach(() => vi.unstubAllGlobals());
describe('shared plan API adapter', () => {
  it('authenticates compile, submit and bounded results on existing services with abort signals', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({})).mockResolvedValueOnce(response({token: 'desktop-owner'}));
    vi.stubGlobal('fetch', fetchMock); await api.bootstrap();
    const controller = new AbortController(), submission = {plan: samplePlan(), binding: sampleBinding(), request_id: 'persisted-id'};
    await planApi.compile({kind: 'graph', workflow: {nodes: []}}, controller.signal);
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/plans/compile');
    await planApi.submit(submission, controller.signal);
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual(submission);
    expect(fetchMock.mock.calls[2][1].headers['X-Studio-Token']).toBe('desktop-owner');
    expect(fetchMock.mock.calls[2][1].signal).toBe(controller.signal);
    await planApi.events('run:a', 27, controller.signal);
    expect(fetchMock.mock.calls[3][0]).toBe('/api/v1/plans/run%3Aa/events?after=27&limit=30&max_bytes=16384');
    await planApi.logs('run:a', 'attempt:1', 1024, controller.signal);
    expect(fetchMock.mock.calls[4][0]).toContain('offset=1024&max_bytes=16384&encoding=text');
  });
  it('does not retry an uncertain submit and uses opaque artifact IDs instead of caller paths', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({code: 'submission_unknown', message: 'uncertain'}, 503));
    vi.stubGlobal('fetch', fetchMock);
    await expect(planApi.submit({plan: samplePlan(), binding: sampleBinding(), request_id: 'same-key'})).rejects.toMatchObject({code: 'submission_unknown'});
    expect(fetchMock).toHaveBeenCalledOnce();
    fetchMock.mockResolvedValue(response({files: []}));
    await planApi.files('run', 'artifact', 'opaque-cursor');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/plans/run/artifacts/artifact/files?after=opaque-cursor&limit=30&max_bytes=16384');
    await planApi.exportLookup('unchanged key');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/plan-exports/lookup?request_id=unchanged%20key');
  });
});
