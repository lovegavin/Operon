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
});
