import { describe, expect, it, vi } from 'vitest';
import { DesktopHostError } from './types';
import { createWebView2Host } from './webview2';
import type { WebView2Bridge, WebView2BridgeEvent } from './webview2';

type Listener = (event: WebView2BridgeEvent) => void;

function makeBridge() {
  const listeners = new Set<Listener>();
  const posted: unknown[] = [];
  const add = vi.fn((_type: 'message', listener: Listener) => {
    listeners.add(listener);
  });
  const remove = vi.fn((_type: 'message', listener: Listener) => {
    listeners.delete(listener);
  });
  const post = vi.fn((message: unknown) => {
    posted.push(message);
  });
  const bridge: WebView2Bridge = {
    addEventListener: add,
    removeEventListener: remove,
    postMessage: post,
  };

  return {
    bridge,
    posted,
    add,
    remove,
    post,
    listeners,
    emit(data: unknown) {
      for (const listener of [...listeners]) listener({ data });
    },
  };
}

function firstRequestId(handler: ReturnType<typeof vi.fn>): string {
  return handler.mock.calls[0][0] as string;
}

describe('createWebView2Host', () => {
  it('posts exactly one one-field readiness message', async () => {
    const { bridge, posted } = makeBridge();
    await createWebView2Host(bridge).ready();

    expect(posted).toEqual([{ type: 'studio-ready' }]);
    expect(Object.keys(posted[0] as Record<string, unknown>)).toEqual(['type']);
  });

  it('posts exact positive and negative ACKs for the active request', async () => {
    const { bridge, posted, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const onClose = vi.fn();
    host.onPrepareClose(onClose);

    emit({ type: 'prepare-close' });
    const first = firstRequestId(onClose);
    await host.acknowledgeDraftFlush(first, true);

    emit({ type: 'prepare-close' });
    const second = onClose.mock.calls[1][0] as string;
    expect(second).not.toBe(first);
    await host.acknowledgeDraftFlush(second, false);

    expect(posted).toEqual([
      { type: 'draft-saved' },
      { type: 'draft-save-failed' },
    ]);
  });

  it('ignores unrelated and malformed host messages', () => {
    const { bridge, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const onClose = vi.fn();
    host.onPrepareClose(onClose);

    for (const data of [undefined, null, 'prepare-close', 42, {}, { type: 'other' }, { type: 1 }]) {
      emit(data);
    }

    expect(onClose).not.toHaveBeenCalled();
  });

  it('coalesces repeated prepare-close while one flush is pending', async () => {
    const { bridge, posted, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const onClose = vi.fn();
    host.onPrepareClose(onClose);

    emit({ type: 'prepare-close' });
    emit({ type: 'prepare-close' });
    emit({ type: 'prepare-close' });

    expect(onClose).toHaveBeenCalledTimes(1);
    await host.acknowledgeDraftFlush(firstRequestId(onClose), true);
    expect(posted).toEqual([{ type: 'draft-saved' }]);
  });

  it('rejects unknown, duplicate and stale ACKs without wire output', async () => {
    const { bridge, posted, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const onClose = vi.fn();
    host.onPrepareClose(onClose);

    await expect(host.acknowledgeDraftFlush('unknown', true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(posted).toEqual([]);

    emit({ type: 'prepare-close' });
    const first = firstRequestId(onClose);
    await host.acknowledgeDraftFlush(first, true);
    expect(posted).toEqual([{ type: 'draft-saved' }]);

    await expect(host.acknowledgeDraftFlush(first, true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(posted).toEqual([{ type: 'draft-saved' }]);

    emit({ type: 'prepare-close' });
    await expect(host.acknowledgeDraftFlush(first, false)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(posted).toEqual([{ type: 'draft-saved' }]);
  });

  it('invalidates pending state, detaches once and mints fresh IDs on resubscribe', async () => {
    const { bridge, posted, remove, listeners, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const firstHandler = vi.fn();
    const unsubscribe = host.onPrepareClose(firstHandler);

    emit({ type: 'prepare-close' });
    const first = firstRequestId(firstHandler);

    unsubscribe();
    expect(remove).toHaveBeenCalledTimes(1);
    expect(listeners.size).toBe(0);
    unsubscribe();
    expect(remove).toHaveBeenCalledTimes(1);

    await expect(host.acknowledgeDraftFlush(first, true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(posted).toEqual([]);

    const secondHandler = vi.fn();
    host.onPrepareClose(secondHandler);
    emit({ type: 'prepare-close' });
    const second = firstRequestId(secondHandler);
    expect(second).not.toBe(first);

    await expect(host.acknowledgeDraftFlush(first, true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    await host.acknowledgeDraftFlush(second, false);
    expect(posted).toEqual([{ type: 'draft-save-failed' }]);
  });

  it('refuses a second close subscriber without stealing ownership', () => {
    const { bridge, add, emit } = makeBridge();
    const host = createWebView2Host(bridge);
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
    expect(add).toHaveBeenCalledTimes(1);

    emit({ type: 'prepare-close' });
    expect(first).toHaveBeenCalledTimes(1);
  });

  it('converts readiness transport errors to typed safe errors', async () => {
    const { bridge, post } = makeBridge();
    post.mockImplementationOnce(() => {
      throw new Error('C:\\private\\token.txt');
    });

    await expect(createWebView2Host(bridge).ready()).rejects.toMatchObject({
      code: 'host_bridge_unavailable',
      message: 'Desktop host bridge failed.',
      request_id: null,
    });
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('converts ACK transport errors and cannot send a duplicate ACK', async () => {
    const { bridge, post, emit } = makeBridge();
    const host = createWebView2Host(bridge);
    const onClose = vi.fn();
    host.onPrepareClose(onClose);
    emit({ type: 'prepare-close' });
    const requestId = firstRequestId(onClose);

    post.mockImplementationOnce(() => {
      throw new Error('transport');
    });
    await expect(host.acknowledgeDraftFlush(requestId, true)).rejects.toMatchObject({
      code: 'host_bridge_unavailable',
    });
    expect(post).toHaveBeenCalledTimes(1);

    await expect(host.acknowledgeDraftFlush(requestId, true)).rejects.toMatchObject({
      code: 'host_request_stale',
    });
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('invalidates a partially registered listener before allowing a later subscription', () => {
    const { bridge, add, emit } = makeBridge();
    const host = createWebView2Host(bridge);

    add.mockImplementationOnce(() => {
      throw new Error('no message channel');
    });
    expect(() => host.onPrepareClose(vi.fn())).toThrow(DesktopHostError);

    const partial = add.mock.calls[0][1];
    const handler = vi.fn();
    const unsubscribe = host.onPrepareClose(handler);

    partial({ data: { type: 'prepare-close' } });
    expect(handler).not.toHaveBeenCalled();

    emit({ type: 'prepare-close' });
    expect(handler).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it('keeps cleanup idempotent when detaching throws', () => {
    const { bridge, remove } = makeBridge();
    const host = createWebView2Host(bridge);
    const unsubscribe = host.onPrepareClose(vi.fn());

    remove.mockImplementationOnce(() => {
      throw new Error('already detached');
    });

    expect(() => unsubscribe()).not.toThrow();
    expect(() => unsubscribe()).not.toThrow();
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it('never dispatches a retained listener into a later subscriber', async () => {
    const { bridge, add, remove, emit, posted } = makeBridge();
    const host = createWebView2Host(bridge);
    const first = vi.fn();
    const unsubscribe = host.onPrepareClose(first);
    const retained = add.mock.calls[0][1];

    remove.mockImplementationOnce(() => {
      throw new Error('cannot detach');
    });
    unsubscribe();

    const second = vi.fn();
    host.onPrepareClose(second);

    // The bridge retained the old listener, but it is inactive now.
    retained({ data: { type: 'prepare-close' } });
    expect(first).not.toHaveBeenCalled();
    expect(second).not.toHaveBeenCalled();

    emit({ type: 'prepare-close' });
    expect(second).toHaveBeenCalledTimes(1);
    const requestId = second.mock.calls[0][0] as string;
    await host.acknowledgeDraftFlush(requestId, true);
    expect(posted).toEqual([{ type: 'draft-saved' }]);
  });
});
