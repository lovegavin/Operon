import { describe, expect, it, vi } from 'vitest';
import { connectCloseHandshake } from './lifecycle';
import { DesktopHostError } from './types';
import type { DesktopHost } from './types';
import { createWebView2Host } from './webview2';
import type { WebView2Bridge, WebView2BridgeEvent } from './webview2';

async function settle(): Promise<void> {
  for (let index = 0; index < 6; index += 1) await Promise.resolve();
}

function makeHost() {
  let handler: ((requestId: string) => void) | null = null;
  const unsubscribe = vi.fn();
  const acknowledge = vi.fn(async (_requestId: string, _saved: boolean) => {});
  const onPrepareClose = vi.fn((next: (requestId: string) => void) => {
    handler = next;
    return unsubscribe;
  });
  const host: DesktopHost = {
    kind: 'browser',
    ready: vi.fn(async () => {}),
    acknowledgeDraftFlush: acknowledge,
    showDiagnostics: vi.fn(async () => {}),
    requestFullExit: vi.fn(async () => {}),
    openCommittedArtifact: vi.fn(async () => {}),
    onPrepareClose,
  };

  return {
    host,
    acknowledge,
    unsubscribe,
    onPrepareClose,
    emit(requestId: string) {
      handler?.(requestId);
    },
  };
}

function makeBridge() {
  const listeners = new Set<(event: WebView2BridgeEvent) => void>();
  const posted: unknown[] = [];
  const bridge: WebView2Bridge = {
    addEventListener: vi.fn((_type: 'message', listener: (event: WebView2BridgeEvent) => void) => {
      listeners.add(listener);
    }),
    removeEventListener: vi.fn((_type: 'message', listener: (event: WebView2BridgeEvent) => void) => {
      listeners.delete(listener);
    }),
    postMessage: vi.fn((message: unknown) => {
      posted.push(message);
    }),
  };

  return {
    bridge,
    posted,
    emit(data: unknown) {
      for (const listener of [...listeners]) listener({ data });
    },
  };
}

describe('connectCloseHandshake', () => {
  it('registers the close listener without flushing or acknowledging early', () => {
    const { host, onPrepareClose, acknowledge } = makeHost();
    const flush = vi.fn();

    const cleanup = connectCloseHandshake(host, flush, vi.fn());

    expect(onPrepareClose).toHaveBeenCalledTimes(1);
    expect(flush).not.toHaveBeenCalled();
    expect(acknowledge).not.toHaveBeenCalled();
    cleanup();
  });

  it('acknowledges a resolved flush as saved', async () => {
    const { host, emit, acknowledge } = makeHost();
    const onError = vi.fn();
    const cleanup = connectCloseHandshake(host, async () => {}, onError);

    emit('close-1');
    await settle();

    expect(acknowledge).toHaveBeenCalledTimes(1);
    expect(acknowledge).toHaveBeenCalledWith('close-1', true);
    expect(onError).not.toHaveBeenCalled();
    cleanup();
  });

  it('acknowledges synchronous and asynchronous flush failures as unsaved', async () => {
    const syncHost = makeHost();
    const syncCleanup = connectCloseHandshake(
      syncHost.host,
      () => {
        throw new Error('sync flush');
      },
      vi.fn(),
    );
    syncHost.emit('close-sync');
    await settle();
    expect(syncHost.acknowledge).toHaveBeenCalledWith('close-sync', false);
    syncCleanup();

    const asyncHost = makeHost();
    const asyncCleanup = connectCloseHandshake(
      asyncHost.host,
      () => Promise.reject(new Error('async flush')),
      vi.fn(),
    );
    asyncHost.emit('close-async');
    await settle();
    expect(asyncHost.acknowledge).toHaveBeenCalledWith('close-async', false);
    asyncCleanup();
  });

  it('reports a failed ACK once without sending a second ACK', async () => {
    const { host, emit, acknowledge } = makeHost();
    const failure = new DesktopHostError(
      'host_bridge_unavailable',
      'Desktop host bridge failed.',
    );
    acknowledge.mockRejectedValueOnce(failure);
    const onError = vi.fn();
    const cleanup = connectCloseHandshake(host, async () => {}, onError);

    emit('close-1');
    await settle();

    expect(acknowledge).toHaveBeenCalledTimes(1);
    expect(acknowledge).toHaveBeenCalledWith('close-1', true);
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(failure);
    cleanup();
  });

  it('reports a synchronous ACK throw once as a typed error', async () => {
    const { host, emit, acknowledge } = makeHost();
    acknowledge.mockImplementationOnce(() => {
      throw new Error('ack transport');
    });
    const onError = vi.fn();
    const cleanup = connectCloseHandshake(host, async () => {}, onError);

    emit('close-1');
    await settle();

    expect(acknowledge).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toMatchObject({
      code: 'host_bridge_unavailable',
      message: 'Desktop host bridge failed.',
    });
    cleanup();
  });

  it('cleans up once and suppresses a late ACK while a flush is unresolved', async () => {
    const { host, emit, acknowledge, unsubscribe } = makeHost();
    let resolveFlush!: () => void;
    const flush = vi.fn(() => new Promise<void>((resolve) => {
      resolveFlush = resolve;
    }));
    const cleanup = connectCloseHandshake(host, flush, vi.fn());

    emit('close-1');
    expect(flush).toHaveBeenCalledTimes(1);
    cleanup();
    cleanup();
    expect(unsubscribe).toHaveBeenCalledTimes(1);

    resolveFlush();
    await settle();
    expect(acknowledge).not.toHaveBeenCalled();

    emit('close-2');
    expect(flush).toHaveBeenCalledTimes(1);
    await settle();
    expect(acknowledge).not.toHaveBeenCalled();
  });

  it('does not ACK a newer close from an older unresolved flush after resubscribe', async () => {
    const { bridge, posted, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    let resolveFirst!: () => void;
    const firstFlush = vi.fn(() => new Promise<void>((resolve) => {
      resolveFirst = resolve;
    }));
    const firstCleanup = connectCloseHandshake(host, firstFlush, vi.fn());

    emit({ type: 'prepare-close' });
    expect(firstFlush).toHaveBeenCalledTimes(1);
    firstCleanup();

    const secondFlush = vi.fn(async () => {});
    const secondCleanup = connectCloseHandshake(host, secondFlush, vi.fn());

    emit({ type: 'prepare-close' });
    expect(secondFlush).toHaveBeenCalledTimes(1);
    await settle();
    expect(posted).toEqual([{ type: 'draft-saved' }]);

    resolveFirst();
    await settle();
    expect(posted).toEqual([{ type: 'draft-saved' }]);

    secondCleanup();
  });
});
