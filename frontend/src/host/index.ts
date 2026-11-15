import type { DesktopHost } from './types';
import { createBrowserHost } from './browser';
import { createTauriHost, toTauriBridge } from './tauri';
import { createWebView2Host, isWebView2Bridge } from './webview2';

export { createBrowserHost } from './browser';
export {
  createTauriHost,
  isTauriBridge,
  toTauriBridge,
} from './tauri';
export type {
  TauriBridge,
  TauriBridgeEvent,
  TauriPrepareClosePayload,
} from './tauri';
export { createWebView2Host, isWebView2Bridge } from './webview2';
export type { WebView2Bridge, WebView2BridgeEvent } from './webview2';
export { connectCloseHandshake } from './lifecycle';
export type { CloseErrorHandler, CloseFlush } from './lifecycle';

interface DesktopHostScope {
  chrome?: { webview?: unknown };
  __TAURI__?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isDesktopHostScope(value: unknown): value is DesktopHostScope {
  return isRecord(value) && ('chrome' in value || '__TAURI__' in value);
}

/**
 * Testable selection: Tauri wins only when both host APIs are present, then a
 * complete WebView2 bridge, otherwise the safe browser host. The first
 * argument may be a WebView2 bridge, a Tauri scope, or a full window-like
 * scope. Importing this module never probes the global scope.
 */
export function selectDesktopHost(
  webview: unknown,
  tauri: unknown = undefined,
): DesktopHost {
  const scope = isDesktopHostScope(webview) ? webview : null;
  const tauriCandidate = tauri !== undefined
    ? tauri
    : (scope !== null ? scope.__TAURI__ : webview);
  const tauriBridge = toTauriBridge(tauriCandidate);
  if (tauriBridge !== null) return createTauriHost(tauriBridge);

  const webviewCandidate = scope !== null ? scope.chrome?.webview : webview;
  return isWebView2Bridge(webviewCandidate)
    ? createWebView2Host(webviewCandidate)
    : createBrowserHost();
}

/** Select at call time; importing this module never posts readiness. */
export function createDesktopHost(): DesktopHost {
  if (typeof window === 'undefined') return createBrowserHost();
  const scope = window as unknown as DesktopHostScope;
  return selectDesktopHost(scope.chrome?.webview, scope.__TAURI__);
}
