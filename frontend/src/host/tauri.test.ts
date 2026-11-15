import { describe, expect, it, vi } from 'vitest';
import { DesktopHostError } from './types';
import {
  MAX_PREPARE_CLOSE_REQUEST_ID_LENGTH,
  PREPARE_CLOSE_EVENT,
  createTauriHost,
  isTauriBridge,
  toTauriBridge,
} from './tauri';
import type { TauriBridge, TauriBridgeEvent } from './tauri';

type EventHandler = (event: TauriBridgeEvent<unknown>) => void;

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flushMicrotasks(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

function makeBridge() {
  const invoke = vi.fn((_command: string, _args?: Record<string, unknown>) => (
    Promise.resolve(undefined)
  ));
  const defaultUnlisten = vi.fn();
  const registrations: Array<{
    event: string;
    handler: EventHandler;
    gate: Deferred<() => void>;
  }> = [];

  const listen = vi.fn((event: string, handler: EventHandler) => {
    const gate = deferred<() => void>();
    registrations.push({ event, handler, gate });
    return gate.promise;
  });

  const bridge = { invoke, listen } as unknown as TauriBridge;

  return {
    bridge,
    invoke,
    listen,
    unlisten: defaultUnlisten,
    registrations,
    async resolveListen(index = 0, unlisten: () => void = defaultUnlisten) {
      registrations[index]!.gate.resolve(unlisten);
      await flushMicrotasks();
    },
    async rejectListen(index = 0, reason: unknown = new Error('listen failed')) {
      registrations[index]!.gate.reject(reason);
      await flushMicrotasks();
    },
    emit(index: number, payload: unknown) {
      registrations[index]!.handler({ payload });
    },
    emitRaw(index: number, event: unknown) {
      registrations[index]!.handler(event as TauriBridgeEvent<unknown>);
    },
  };
}

describe('createTauriHost', () => {
  it('waits for in-flight listener registration before invoking ready', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    host.onPrepareClose(vi.fn());

    const ready = host.ready();
    await flushMicrotasks();

    expect(hostBridge.listen).toHaveBeenCalledTimes(1);
    expect(hostBridge.listen).toHaveBeenCalledWith(
      PREPARE_CLOSE_EVENT,
      expect.any(Function),
    );
    expect(hostBridge.invoke).not.toHaveBeenCalled();

    await hostBridge.resolveListen();
    await ready;

    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);
    expect(hostBridge.invoke).toHaveBeenCalledWith('ready');
  });

  it('does not let an old listen completion release readiness early', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const unsubscribe = host.onPrepareClose(vi.fn());
    const ready = host.ready();
    unsubscribe();

    host.onPrepareClose(vi.fn());
    await hostBridge.resolveListen(0, vi.fn());

    expect(hostBridge.invoke).not.toHaveBeenCalled();
    await hostBridge.resolveListen(1, vi.fn());
    await ready;

    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);
    expect(hostBridge.invoke).toHaveBeenCalledWith('ready');
  });

  it('correlates native request IDs with the exact RPC surface', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const handler = vi.fn();
    host.onPrepareClose(handler);
    await hostBridge.resolveListen();

    hostBridge.emit(0, { request_id: 'close-1' });
    hostBridge.emit(0, { request_id: 'close-1' });
    await host.acknowledgeDraftFlush('close-1', true);

    hostBridge.emit(0, { request_id: 'close-2' });
    await host.acknowledgeDraftFlush('close-2', false);

    await host.showDiagnostics();
    await host.requestFullExit();
    await host.openCommittedArtifact('run-1', 'artifact-2', 'file-3');

    expect(handler.mock.calls).toEqual([['close-1'], ['close-2']]);
    expect(hostBridge.invoke.mock.calls).toEqual([
      ['acknowledge_draft_flush', { requestId: 'close-1', saved: true }],
      ['acknowledge_draft_flush', { requestId: 'close-2', saved: false }],
      ['show_diagnostics'],
      ['request_full_exit'],
      ['open_committed_artifact', {
        runId: 'run-1',
        artifactId: 'artifact-2',
        fileId: 'file-3',
      }],
    ]);
  });

  it('exposes a rejected listener registration through ready', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    host.onPrepareClose(vi.fn());
    await hostBridge.rejectListen(0, new Error('listen rejected'));

    await expect(host.ready()).rejects.toMatchObject({
      code: 'host_bridge_unavailable',
      message: 'Desktop host bridge failed.',
      request_id: null,
      retryable: false,
      next_actions: [],
    });
    expect(hostBridge.invoke).not.toHaveBeenCalled();
  });

  it('preserves a valid HostErrorShape from a rejected registration', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const shape = {
      code: 'host_capability_unavailable' as const,
      message: 'Native event channel denied.',
      request_id: 'close-denied',
      retryable: false,
      next_actions: ['retry' as const],
    };
    host.onPrepareClose(vi.fn());
    await hostBridge.rejectListen(0, shape);

    await expect(host.ready()).rejects.toMatchObject(shape);
    expect(hostBridge.invoke).not.toHaveBeenCalled();
  });

  it('unsubscribes immediately when listen resolves after cleanup', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const handler = vi.fn();
    const unsubscribe = host.onPrepareClose(handler);
    unsubscribe();

    expect(hostBridge.unlisten).not.toHaveBeenCalled();
    await hostBridge.resolveListen(0, hostBridge.unlisten);
    expect(hostBridge.unlisten).toHaveBeenCalledTimes(1);

    hostBridge.emit(0, { request_id: 'late' });
    expect(handler).not.toHaveBeenCalled();
    await expect(host.acknowledgeDraftFlush('late', true)).rejects.toMatchObject({
      code: 'host_request_stale',
      request_id: 'late',
    });
    expect(hostBridge.invoke).not.toHaveBeenCalled();
  });

  it('keeps a new subscription isolated from an old listen completion', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const first = vi.fn();
    const unsubscribeFirst = host.onPrepareClose(first);
    unsubscribeFirst();

    const second = vi.fn();
    host.onPrepareClose(second);
    const oldUnlisten = vi.fn();
    const newUnlisten = vi.fn();

    await hostBridge.resolveListen(1, newUnlisten);
    await hostBridge.resolveListen(0, oldUnlisten);

    expect(oldUnlisten).toHaveBeenCalledTimes(1);
    expect(newUnlisten).not.toHaveBeenCalled();

    hostBridge.emit(0, { request_id: 'old-close' });
    expect(first).not.toHaveBeenCalled();
    expect(second).not.toHaveBeenCalled();

    hostBridge.emit(1, { request_id: 'new-close' });
    expect(second).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledWith('new-close');

    await host.acknowledgeDraftFlush('new-close', true);
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);
    expect(hostBridge.invoke).toHaveBeenCalledWith(
      'acknowledge_draft_flush',
      { requestId: 'new-close', saved: true },
    );
  });

  it('rejects unknown, duplicate and stale ACKs locally', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const handler = vi.fn();
    const unsubscribe = host.onPrepareClose(handler);
    await hostBridge.resolveListen();

    await expect(host.acknowledgeDraftFlush('unknown', true)).rejects.toMatchObject({
      code: 'host_request_stale',
      request_id: 'unknown',
    });
    expect(hostBridge.invoke).not.toHaveBeenCalled();

    hostBridge.emit(0, { request_id: 'close-1' });
    await host.acknowledgeDraftFlush('close-1', true);
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);

    await expect(host.acknowledgeDraftFlush('close-1', true)).rejects.toMatchObject({
      code: 'host_request_stale',
      request_id: 'close-1',
    });
    await expect(host.acknowledgeDraftFlush('close-1', false)).rejects.toMatchObject({
      code: 'host_request_stale',
      request_id: 'close-1',
    });
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);

    hostBridge.emit(0, { request_id: 'close-2' });
    expect(handler).toHaveBeenCalledTimes(2);
    unsubscribe();
    await expect(host.acknowledgeDraftFlush('close-2', true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    hostBridge.emit(0, { request_id: 'close-3' });
    expect(handler).toHaveBeenCalledTimes(2);
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);
  });

  it('ignores malformed prepare-close payloads', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const handler = vi.fn();
    host.onPrepareClose(handler);
    await hostBridge.resolveListen();

    const malformed = [
      undefined,
      null,
      42,
      'prepare-close',
      [],
      {},
      { payload: null },
      { payload: 'prepare-close' },
      { payload: {} },
      { payload: { request_id: '' } },
      { payload: { request_id: '   ' } },
      { payload: { request_id: 42 } },
      { payload: { request_id: 'x'.repeat(MAX_PREPARE_CLOSE_REQUEST_ID_LENGTH + 1) } },
    ];

    for (const event of malformed) hostBridge.emitRaw(0, event);
    expect(handler).not.toHaveBeenCalled();

    hostBridge.emit(0, { request_id: 'valid-close' });
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith('valid-close');
  });

  it('normalizes ACK transport failure and cannot send a second ACK', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const handler = vi.fn();
    host.onPrepareClose(handler);
    await hostBridge.resolveListen();
    hostBridge.emit(0, { request_id: 'close-1' });

    hostBridge.invoke.mockRejectedValueOnce(new Error('C:\\private\\token.txt'));
    await expect(host.acknowledgeDraftFlush('close-1', true)).rejects.toMatchObject({
      code: 'host_bridge_unavailable',
      message: 'Desktop host bridge failed.',
      request_id: null,
    });
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);

    await expect(host.acknowledgeDraftFlush('close-1', false)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(hostBridge.invoke).toHaveBeenCalledTimes(1);
  });

  it('normalizes other command failures and preserves valid shapes', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const shape = {
      code: 'host_capability_unavailable' as const,
      message: 'Diagnostics are unavailable.',
      request_id: null,
      retryable: false,
      next_actions: ['open_host_logs' as const],
    };

    hostBridge.invoke.mockRejectedValueOnce(new Error('offline'));
    await expect(host.ready()).rejects.toMatchObject({
      code: 'host_bridge_unavailable',
      message: 'Desktop host bridge failed.',
    });

    hostBridge.invoke.mockRejectedValueOnce(shape);
    await expect(host.showDiagnostics()).rejects.toMatchObject(shape);
  });

  it('refuses a second close subscriber and keeps the first', async () => {
    const hostBridge = makeBridge();
    const host = createTauriHost(hostBridge.bridge);
    const first = vi.fn();
    host.onPrepareClose(first);

    let caught: unknown;
    try {
      host.onPrepareClose(vi.fn());
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(DesktopHostError);
    expect(caught).toMatchObject({ code: 'host_bridge_unavailable' });
    expect(hostBridge.listen).toHaveBeenCalledTimes(1);

    await hostBridge.resolveListen();
    hostBridge.emit(0, { request_id: 'close-1' });
    expect(first).toHaveBeenCalledTimes(1);
  });

  it('recognizes complete flat and window-shaped bridges', () => {
    const invoke = vi.fn();
    const listen = vi.fn();
    expect(isTauriBridge({ invoke, listen })).toBe(true);
    expect(isTauriBridge({ invoke })).toBe(false);
    expect(isTauriBridge(null)).toBe(false);

    expect(toTauriBridge({ invoke, listen })).toEqual({ invoke, listen });
    expect(toTauriBridge({ core: { invoke }, event: { listen } })).not.toBeNull();
    expect(toTauriBridge({ core: { invoke } })).toBeNull();
    expect(toTauriBridge(undefined)).toBeNull();
  });

  it('does not depend on a Tauri SDK module', () => {
    // @ts-ignore Vite provides import.meta.glob during the test transform.
    const sources = import.meta.glob(['./index.ts', './tauri.ts'], {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;

    expect(Object.keys(sources)).toHaveLength(2);
    for (const source of Object.values(sources)) {
      expect(source).not.toMatch(/@tauri-apps/);
    }
  });
});
