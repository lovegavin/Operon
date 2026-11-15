import { describe, expect, it, vi } from 'vitest';
import { createBrowserHost } from './browser';

describe('createBrowserHost', () => {
  it('has no side effects for readiness or close subscription', async () => {
    const host = createBrowserHost();
    const handler = vi.fn();
    expect(host.kind).toBe('browser');

    await expect(host.ready()).resolves.toBeUndefined();
    const unsubscribe = host.onPrepareClose(handler);
    expect(handler).not.toHaveBeenCalled();
    unsubscribe();
    unsubscribe();
    expect(handler).not.toHaveBeenCalled();
  });

  it('rejects acknowledgements as stale without wire output', async () => {
    const host = createBrowserHost();
    await expect(host.acknowledgeDraftFlush('close-1', true)).rejects.toMatchObject({
      name: 'DesktopHostError',
      code: 'host_request_stale',
      request_id: 'close-1',
      next_actions: [],
    });
  });

  it('rejects privileged capabilities with safe next actions', async () => {
    const host = createBrowserHost();

    await expect(host.showDiagnostics()).rejects.toMatchObject({
      code: 'host_capability_unavailable',
      next_actions: ['open_host_logs'],
    });
    await expect(host.requestFullExit()).rejects.toMatchObject({
      code: 'host_capability_unavailable',
      next_actions: ['use_tray_menu_exit'],
    });
    await expect(host.openCommittedArtifact('run', 'artifact', 'file')).rejects.toMatchObject({
      code: 'host_capability_unavailable',
      next_actions: ['use_http_artifact_link'],
    });
  });
});
