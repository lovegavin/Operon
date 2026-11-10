import {afterEach, describe, expect, it, vi} from 'vitest';

afterEach(() => {vi.unstubAllGlobals(); vi.resetModules();});
describe('shared application preferences', () => {
  it('reads and writes one current configuration object', async () => {
    const initial = JSON.stringify({language: 'en', theme: 'dark'});
    const values = new Map([['operon-studio-config-v1', initial]]);
    vi.stubGlobal('localStorage', {getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value)});
    const prefs = await import('./preferences');
    expect(prefs.getPreferences()).toEqual({language: 'en', theme: 'dark'});
    prefs.setPreferences({theme: 'light'});
    expect(JSON.parse(values.get('operon-studio-config-v1')!)).toEqual({language: 'en', theme: 'light'});
    vi.resetModules();
    expect((await import('./preferences')).getPreferences()).toEqual({language: 'en', theme: 'light'});
  });
  it('serializes updates so a slow theme response cannot undo a newer language choice', async () => {
    const finish: ((value: unknown) => void)[] = [];
    const fetch = vi.fn(() => new Promise(resolve => finish.push(resolve)));
    vi.stubGlobal('fetch', fetch);
    const {api} = await import('./api');
    const theme = api.savePreferences({theme: 'dark'});
    const language = api.savePreferences({language: 'en'});
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    finish[0]({ok: true, json: async () => ({language: 'system', theme: 'dark'})});
    await theme;
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    finish[1]({ok: true, json: async () => ({language: 'en', theme: 'dark'})});
    expect(await language).toEqual({language: 'en', theme: 'dark'});
  });
});
