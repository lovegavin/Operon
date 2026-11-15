import type { DesktopHost } from './types';
import { createBrowserHost } from './browser';
import { createWebView2Host, isWebView2Bridge } from './webview2';

export { createBrowserHost } from './browser';
export { createWebView2Host, isWebView2Bridge } from './webview2';
export type { WebView2Bridge, WebView2BridgeEvent } from './webview2';
export { connectCloseHandshake } from './lifecycle';
export type { CloseErrorHandler, CloseFlush } from './lifecycle';

interface WebView2Scope {
  chrome?: { webview?: unknown };
}

/**
 * Testable selection: WebView2 only when the injected candidate has the three
 * required methods, otherwise the safe browser host. No Tauri adapter exists.
 */
export function selectDesktopHost(webview: unknown): DesktopHost {
  return isWebView2Bridge(webview)
    ? createWebView2Host(webview)
    : createBrowserHost();
}

/** Select at call time; importing this module never posts readiness. */
export function createDesktopHost(): DesktopHost {
  if (typeof window === 'undefined') return createBrowserHost();
  const scope = window as unknown as WebView2Scope;
  return selectDesktopHost(scope.chrome?.webview);
}
