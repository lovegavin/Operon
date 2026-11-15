import type { DesktopHost } from './types';
import { DesktopHostError, toHostError } from './types';

/** Exact event emitted by the native Tauri host before a full close. */
export const PREPARE_CLOSE_EVENT = 'operon://prepare-close' as const;

/** Host request IDs are untrusted input and must stay bounded. */
export const MAX_PREPARE_CLOSE_REQUEST_ID_LENGTH = 256;

export interface TauriBridgeEvent<T> {
  payload: T;
}

/**
 * Injectable structural subset of the Tauri IPC API. No Tauri SDK module is
 * imported, so the adapter stays usable in browser and WebView2 builds.
 */
export interface TauriBridge {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>;
  listen<T>(
    event: string,
    handler: (event: TauriBridgeEvent<T>) => void,
  ): Promise<() => void>;
}

export interface TauriPrepareClosePayload {
  request_id: string;
}

interface TauriWindowScope {
  __TAURI__?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function isTauriBridge(value: unknown): value is TauriBridge {
  return isRecord(value)
    && typeof value.invoke === 'function'
    && typeof value.listen === 'function';
}

/**
 * Builds the injectable bridge from either `window.__TAURI__` (with `core` and
 * `event` members) or an already-flat bridge. The wrappers call each native
 * method on its owning object because the Tauri APIs rely on their receiver.
 */
export function toTauriBridge(value: unknown): TauriBridge | null {
  if (isTauriBridge(value)) return value;
  if (!isRecord(value)) return null;

  const scope = '__TAURI__' in value ? (value as TauriWindowScope).__TAURI__ : value;
  if (!isRecord(scope)) return null;

  const core = scope.core;
  const event = scope.event;
  if (!isRecord(core) || typeof core.invoke !== 'function') return null;
  if (!isRecord(event) || typeof event.listen !== 'function') return null;

  const invoke = core.invoke as (
    command: string,
    args?: Record<string, unknown>,
  ) => Promise<unknown>;
  const listen = event.listen as (
    eventName: string,
    handler: (event: TauriBridgeEvent<unknown>) => void,
  ) => Promise<() => void>;

  return {
    invoke: async <T>(command: string, args?: Record<string, unknown>) => {
      const result = args === undefined
        ? await invoke.call(core, command)
        : await invoke.call(core, command, args);
      return result as T;
    },
    listen: <T>(
      eventName: string,
      handler: (event: TauriBridgeEvent<T>) => void,
    // The host API is transport-typed as unknown; the public bridge restores T.
    ) => listen.call(
      event,
      eventName,
      handler as unknown as (event: TauriBridgeEvent<unknown>) => void,
    ),
  };
}

function bridgeUnavailable(message: string): DesktopHostError {
  return new DesktopHostError('host_bridge_unavailable', message, null, false, []);
}

function staleAcknowledgement(requestId: string): DesktopHostError {
  const correlationId = typeof requestId === 'string' && requestId.length > 0
    ? requestId
    : null;
  return new DesktopHostError(
    'host_request_stale',
    'No pending close request matches this acknowledgement.',
    correlationId,
  );
}

function readPrepareCloseRequestId(event: unknown): string | null {
  if (!isRecord(event)) return null;
  const payload = event.payload;
  if (!isRecord(payload)) return null;

  const requestId = payload.request_id;
  if (typeof requestId !== 'string') return null;
  if (requestId.length === 0) return null;
  if (requestId.length > MAX_PREPARE_CLOSE_REQUEST_ID_LENGTH) return null;
  if (requestId.trim().length === 0) return null;
  return requestId;
}

function callUnlisten(unlisten: unknown): void {
  if (typeof unlisten !== 'function') return;
  try {
    unlisten();
  } catch {
    // Cleanup must not throw into an effect teardown. The lifecycle closure is
    // already inactive, so a retained native listener remains harmless.
  }
}

async function callCommand<T>(
  bridge: TauriBridge,
  command: string,
  args?: Record<string, unknown>,
): Promise<T> {
  try {
    return args === undefined
      ? await bridge.invoke<T>(command)
      : await bridge.invoke<T>(command, args);
  } catch (error) {
    throw toHostError(error);
  }
}

interface CloseLifecycle {
  handler: (requestId: string) => void;
  active: boolean;
  detachRequested: boolean;
  failure: DesktopHostError | null;
  pendingIds: Set<string>;
  seenIds: Set<string>;
  unlisten: (() => void) | null;
  readyGate: Promise<void>;
  resolveReady: () => void;
}

export function createTauriHost(bridge: TauriBridge): DesktopHost {
  let current: CloseLifecycle | null = null;

  const failRegistration = (lifecycle: CloseLifecycle, error: unknown): void => {
    if (lifecycle.failure === null) lifecycle.failure = toHostError(error);
    lifecycle.pendingIds.clear();
    lifecycle.resolveReady();
  };

  const settleRegistration = (
    lifecycle: CloseLifecycle,
    unlisten: unknown,
  ): void => {
    // Cleanup can happen while listen() is still pending. A late resolution is
    // detached immediately and never touches a newer lifecycle.
    if (!lifecycle.active || current !== lifecycle || lifecycle.detachRequested) {
      callUnlisten(unlisten);
      lifecycle.resolveReady();
      return;
    }

    if (typeof unlisten !== 'function') {
      failRegistration(
        lifecycle,
        bridgeUnavailable('Tauri event registration did not return an unsubscribe function.'),
      );
      return;
    }

    lifecycle.unlisten = unlisten;
    lifecycle.resolveReady();
  };

  return {
    kind: 'tauri',

    async ready() {
      let lifecycle = current;
      while (lifecycle !== null) {
        await lifecycle.readyGate;

        // A registration can be replaced while this call is waiting. Only the
        // subscription that is current when it settles may gate readiness.
        if (current !== lifecycle) {
          lifecycle = current;
          continue;
        }

        if (lifecycle.failure !== null) throw lifecycle.failure;
        break;
      }

      await callCommand<void>(bridge, 'ready');
    },

    async acknowledgeDraftFlush(requestId, saved) {
      const lifecycle = current;
      if (lifecycle === null || !lifecycle.pendingIds.has(requestId)) {
        throw staleAcknowledgement(requestId);
      }

      // Remove before the RPC so a transport failure cannot be retried into a
      // second, contradictory ACK for the same close lifecycle.
      lifecycle.pendingIds.delete(requestId);
      await callCommand<void>(bridge, 'acknowledge_draft_flush', {
        requestId,
        saved,
      });
    },

    async showDiagnostics() {
      await callCommand<void>(bridge, 'show_diagnostics');
    },

    async requestFullExit() {
      await callCommand<void>(bridge, 'request_full_exit');
    },

    async openCommittedArtifact(runId, artifactId, fileId) {
      await callCommand<void>(bridge, 'open_committed_artifact', {
        runId,
        artifactId,
        fileId,
      });
    },

    onPrepareClose(handler) {
      if (current !== null) {
        throw new DesktopHostError(
          'host_bridge_unavailable',
          'A close-handshake listener is already registered for this host.',
        );
      }

      let resolveReady!: () => void;
      const readyGate = new Promise<void>((resolve) => {
        resolveReady = resolve;
      });

      const lifecycle: CloseLifecycle = {
        handler,
        active: true,
        detachRequested: false,
        failure: null,
        pendingIds: new Set<string>(),
        seenIds: new Set<string>(),
        unlisten: null,
        readyGate,
        resolveReady,
      };
      current = lifecycle;

      const listener = (event: TauriBridgeEvent<unknown>) => {
        if (!lifecycle.active || current !== lifecycle) return;
        if (lifecycle.failure !== null) return;

        const requestId = readPrepareCloseRequestId(event);
        if (requestId === null) return;

        // The native host owns correlation IDs. Repeated events for one ID are
        // coalesced, and a reused ID is treated as duplicate rather than a new
        // close attempt.
        if (lifecycle.pendingIds.has(requestId) || lifecycle.seenIds.has(requestId)) {
          return;
        }

        lifecycle.pendingIds.add(requestId);
        lifecycle.seenIds.add(requestId);
        lifecycle.handler(requestId);
      };

      const detach = () => {
        if (!lifecycle.active) return;
        lifecycle.active = false;
        lifecycle.pendingIds.clear();
        lifecycle.seenIds.clear();
        if (current === lifecycle) current = null;

        const unlisten = lifecycle.unlisten;
        lifecycle.unlisten = null;
        if (unlisten !== null) {
          callUnlisten(unlisten);
        } else {
          lifecycle.detachRequested = true;
        }
      };

      let pending: Promise<() => void>;
      try {
        pending = bridge.listen(PREPARE_CLOSE_EVENT, listener);
      } catch (error) {
        failRegistration(lifecycle, error);
        return detach;
      }

      void Promise.resolve(pending).then(
        (unlisten) => settleRegistration(lifecycle, unlisten),
        (error) => failRegistration(lifecycle, error),
      );

      return detach;
    },
  };
}
