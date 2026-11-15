import { describe, expect, it, vi } from 'vitest';
import { createDesktopHost, selectDesktopHost } from './index';
import type { WebView2Bridge } from './webview2';

function completeBridge(): WebView2Bridge {
  return {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    postMessage: vi.fn(),
  };
}

function completeTauri() {
  return {
    core: { invoke: vi.fn() },
    event: { listen: vi.fn() },
  };
}

describe('desktop host selection', () => {
  it('uses the browser host with no window or bridge', () => {
    expect(typeof window).toBe('undefined');
    expect(selectDesktopHost(undefined).kind).toBe('browser');
    expect(createDesktopHost().kind).toBe('browser');
  });

  it('uses the browser host for an incomplete bridge', () => {
    expect(selectDesktopHost({ postMessage: vi.fn() }).kind).toBe('browser');
    expect(selectDesktopHost({
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }).kind).toBe('browser');
    expect(selectDesktopHost({
      addEventListener: vi.fn(),
      postMessage: vi.fn(),
    }).kind).toBe('browser');
    expect(selectDesktopHost(null).kind).toBe('browser');
  });

  it('uses the WebView2 host for a complete bridge', () => {
    expect(selectDesktopHost(completeBridge()).kind).toBe('webview2');
  });

  it('prefers a complete Tauri scope over WebView2', () => {
    expect(selectDesktopHost(completeBridge(), completeTauri()).kind).toBe('tauri');
    expect(selectDesktopHost({
      chrome: { webview: completeBridge() },
      __TAURI__: completeTauri(),
    }).kind).toBe('tauri');
  });

  it('falls back to WebView2 when the Tauri scope is incomplete', () => {
    const webview = completeBridge();

    expect(selectDesktopHost(webview, undefined).kind).toBe('webview2');
    expect(selectDesktopHost(webview, null).kind).toBe('webview2');
    expect(selectDesktopHost(webview, {}).kind).toBe('webview2');
    expect(selectDesktopHost(webview, { core: { invoke: vi.fn() } }).kind).toBe('webview2');
    expect(selectDesktopHost(webview, { event: { listen: vi.fn() } }).kind).toBe('webview2');
    expect(selectDesktopHost(webview, {
      core: {},
      event: { listen: vi.fn() },
    }).kind).toBe('webview2');
    expect(selectDesktopHost(webview, {
      core: { invoke: vi.fn() },
      event: {},
    }).kind).toBe('webview2');
  });

  it('uses Tauri without WebView2 and browser for incomplete candidates', () => {
    expect(selectDesktopHost(completeTauri()).kind).toBe('tauri');
    expect(selectDesktopHost(undefined, completeTauri()).kind).toBe('tauri');
    expect(selectDesktopHost(undefined, { core: { invoke: vi.fn() } }).kind).toBe('browser');
    expect(selectDesktopHost(undefined, undefined).kind).toBe('browser');
  });

  it('selects Tauri from window.__TAURI__ at creation time', () => {
    vi.stubGlobal('window', {
      __TAURI__: completeTauri(),
      chrome: { webview: completeBridge() },
    });
    try {
      expect(createDesktopHost().kind).toBe('tauri');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('wraps Tauri host APIs with their owning receiver', async () => {
    const receivers: unknown[] = [];
    const core = {
      invoke(this: unknown) {
        receivers.push(this);
        return Promise.resolve(undefined);
      },
    };
    const event = {
      listen(this: unknown) {
        receivers.push(this);
        return Promise.resolve(() => {});
      },
    };

    const host = selectDesktopHost(undefined, { core, event });
    host.onPrepareClose(vi.fn());
    await host.ready();

    expect(receivers).toHaveLength(2);
    expect(receivers[0]).toBe(event);
    expect(receivers[1]).toBe(core);
  });
});
