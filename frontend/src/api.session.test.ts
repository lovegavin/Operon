import {afterEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';

afterEach(() => vi.unstubAllGlobals());

const reply = (status: number, value: unknown) => ({ok: status < 400, status, json: async () => value});

describe('session token rotation', () => {
  it('refreshes the token and retries once after a stale-session 403', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(reply(403, {message: '本地会话已更新，请刷新页面。'}))
      .mockResolvedValueOnce(reply(200, {token: 'fresh-token'}))
      .mockResolvedValueOnce(reply(200, {environments: {}}));
    vi.stubGlobal('fetch', fetchMock);
    const value = await api.remotePrepareEnvironments('profile-1', ['openmm81']);
    expect(value).toEqual({environments: {}});
    expect(fetchMock.mock.calls[0][0]).toBe('/api/remote/profile-1/environments/prepare');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/bootstrap');
    expect(fetchMock.mock.calls[2][0]).toBe('/api/remote/profile-1/environments/prepare');
    expect(fetchMock.mock.calls[2][1].headers['X-Studio-Token']).toBe('fresh-token');
  });

  it('surfaces the original failure when bootstrap cannot rotate the token', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(reply(403, {message: '本地会话已更新，请刷新页面。'}))
      .mockResolvedValueOnce(reply(500, {message: 'unavailable'}));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api.remoteEnvironmentRetry('profile-1', 'genomics')).rejects.toThrow('本地会话已更新');
    expect(fetchMock.mock.calls).toHaveLength(2);
  });
});
