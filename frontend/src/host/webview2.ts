import type { DesktopHost } from './types';
import {
  DesktopHostError,
  PREPARE_CLOSE_TYPE,
  createLegacyWireMessage,
  toHostError,
} from './types';

/** Structural subset of the WebView2 message API; never a global side effect. */
export interface WebView2BridgeEvent {
  readonly data?: unknown;
}

export interface WebView2Bridge {
  addEventListener(type: 'message', listener: (event: WebView2BridgeEvent) => void): void;
  removeEventListener(type: 'message', listener: (event: WebView2BridgeEvent) => void): void;
  postMessage(message: unknown): void;
}

export function isWebView2Bridge(value: unknown): value is WebView2Bridge {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.addEventListener === 'function'
    && typeof candidate.removeEventListener === 'function'
    && typeof candidate.postMessage === 'function';
}

function capabilityUnavailable(
  message: string,
  nextAction: 'open_host_logs' | 'use_tray_menu_exit' | 'use_http_artifact_link',
): DesktopHostError {
  return new DesktopHostError(
    'host_capability_unavailable',
    message,
    null,
    false,
    [nextAction],
  );
}

/**
 * Module-wide sequence so adapter-local close IDs stay distinct across
 * subscriptions and across adapter instances. These IDs never reach the wire.
 */
let closeSequence = 0;

export function createWebView2Host(bridge: WebView2Bridge): DesktopHost {
  let subscriber: ((requestId: string) => void) | null = null;
  let pendingId: string | null = null;

  return {
    kind: 'webview2',
    async ready() {
      try {
        bridge.postMessage(createLegacyWireMessage('studioReady'));
      } catch (error) {
        throw toHostError(error);
      }
    },
    async acknowledgeDraftFlush(requestId, saved) {
      if (pendingId === null || pendingId !== requestId) {
        throw new DesktopHostError(
          'host_request_stale',
          'No pending close request matches this acknowledgement.',
          requestId,
        );
      }
      // Clear before posting so a transport failure cannot cause a retry to
      // send a second ACK for the same close lifecycle.
      pendingId = null;
      try {
        bridge.postMessage(
          createLegacyWireMessage(saved ? 'draftSaved' : 'draftSaveFailed'),
        );
      } catch (error) {
        throw toHostError(error);
      }
    },
    async showDiagnostics() {
      throw capabilityUnavailable(
        'Host diagnostics require a host IPC that the current WebView2 host does not expose.',
        'open_host_logs',
      );
    },
    async requestFullExit() {
      throw capabilityUnavailable(
        'Full exit is owned by the host tray menu in the current WebView2 host.',
        'use_tray_menu_exit',
      );
    },
    async openCommittedArtifact() {
      throw capabilityUnavailable(
        'Use the existing HTTP artifact link in the current WebView2 host.',
        'use_http_artifact_link',
      );
    },
    onPrepareClose(handler) {
      if (subscriber !== null) {
        throw new DesktopHostError(
          'host_bridge_unavailable',
          'A close-handshake listener is already registered for this host.',
        );
      }

      subscriber = handler;
      pendingId = null;

      // Each subscription owns its listener closure. A listener retained by the
      // bridge after a failed detach stays inactive and cannot dispatch into a
      // later subscriber.
      let active = true;
      const listener = (event: WebView2BridgeEvent) => {
        if (!active || subscriber !== handler) return;
        const data = event?.data;
        if (!data || typeof data !== 'object') return;
        if ((data as { type?: unknown }).type !== PREPARE_CLOSE_TYPE) return;
        if (pendingId !== null) return;

        const requestId = `webview2-close-${++closeSequence}`;
        pendingId = requestId;
        handler(requestId);
      };

      const detach = () => {
        if (!active) return;
        // Mark inactive before detaching so a retained listener is harmless.
        active = false;
        if (subscriber === handler) subscriber = null;
        pendingId = null;
        try {
          bridge.removeEventListener('message', listener);
        } catch {
          // Cleanup must not throw into a React effect teardown. The closure is
          // already inactive, so a retained listener remains harmless.
        }
      };

      try {
        bridge.addEventListener('message', listener);
      } catch (error) {
        // A partial registration may have retained the listener; invalidate it
        // before reporting the transport failure.
        active = false;
        if (subscriber === handler) subscriber = null;
        pendingId = null;
        try {
          bridge.removeEventListener('message', listener);
        } catch {
          // Best-effort detach; the closure is already inactive.
        }
        throw toHostError(error);
      }

      return detach;
    },
  };
}
