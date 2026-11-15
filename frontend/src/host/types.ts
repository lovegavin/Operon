/**
 * Shared T01 DesktopHost contract.
 *
 * This file is transport-neutral. It contains no Tauri, WebView2 or DOM
 * adapters and grants no process, file or shell capabilities.
 */

export type HostKind = 'browser' | 'webview2' | 'tauri';

export const HOST_ERROR_CODES = [
  'host_unsupported',
  'host_capability_unavailable',
  'host_request_stale',
  'host_bridge_unavailable',
] as const;

export type HostErrorCode = (typeof HOST_ERROR_CODES)[number];

export const HOST_NEXT_ACTIONS = [
  'use_tray_menu_exit',
  'open_host_logs',
  'use_http_artifact_link',
  'retry',
] as const;

export type HostNextAction = (typeof HOST_NEXT_ACTIONS)[number];

export interface HostErrorShape {
  code: HostErrorCode;
  message: string;
  request_id: string | null;
  retryable: boolean;
  next_actions: HostNextAction[];
}

export class DesktopHostError extends Error implements HostErrorShape {
  constructor(
    public readonly code: HostErrorCode,
    message: string,
    public readonly request_id: string | null = null,
    public readonly retryable = false,
    next_actions: HostNextAction[] = [],
  ) {
    super(message);
    this.name = 'DesktopHostError';
    this.next_actions = [...next_actions];
  }

  readonly next_actions: HostNextAction[];

  /** Stable serializable shape. Error.message is included explicitly. */
  toJSON(): HostErrorShape {
    return {
      code: this.code,
      message: this.message,
      request_id: this.request_id,
      retryable: this.retryable,
      next_actions: [...this.next_actions],
    };
  }
}

export interface DesktopHost {
  readonly kind: HostKind;
  ready(): Promise<void>;
  acknowledgeDraftFlush(requestId: string, saved: boolean): Promise<void>;
  showDiagnostics(): Promise<void>;
  requestFullExit(): Promise<void>;
  openCommittedArtifact(runId: string, artifactId: string, fileId: string): Promise<void>;
  onPrepareClose(handler: (requestId: string) => void): () => void;
}

/** Exact legacy reply objects understood by the current C# host. */
export type LegacyWireType = 'studio-ready' | 'draft-saved' | 'draft-save-failed';

export interface LegacyWireMessage {
  type: LegacyWireType;
}

export const LEGACY_WIRE = Object.freeze({
  studioReady: Object.freeze({ type: 'studio-ready' as const }),
  draftSaved: Object.freeze({ type: 'draft-saved' as const }),
  draftSaveFailed: Object.freeze({ type: 'draft-save-failed' as const }),
});

export type LegacyWireKind = keyof typeof LEGACY_WIRE;

/**
 * Allocate a fresh one-field message before posting. The legacy C# host must
 * never receive a request ID or any additional property.
 */
export function createLegacyWireMessage(kind: LegacyWireKind): LegacyWireMessage {
  return { type: LEGACY_WIRE[kind].type };
}

export const PREPARE_CLOSE_TYPE = 'prepare-close' as const;

/**
 * Forward Tauri event/ACK DTOs only. No native adapter is implemented in T01.
 */
export interface PrepareCloseEvent {
  readonly type: typeof PREPARE_CLOSE_TYPE;
  readonly request_id: string;
}

export interface AcknowledgeDraftFlushRequest {
  readonly request_id: string;
  readonly saved: boolean;
}

function isHostErrorCode(value: unknown): value is HostErrorCode {
  return typeof value === 'string' && (HOST_ERROR_CODES as readonly string[]).includes(value);
}

function isHostNextAction(value: unknown): value is HostNextAction {
  return typeof value === 'string' && (HOST_NEXT_ACTIONS as readonly string[]).includes(value);
}

/** Validates the complete stable error shape instead of casting a value. */
export function isHostErrorShape(value: unknown): value is HostErrorShape {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return isHostErrorCode(candidate.code)
    && typeof candidate.message === 'string'
    && candidate.message.trim().length > 0
    && (candidate.request_id === null
      || (typeof candidate.request_id === 'string' && candidate.request_id.length > 0))
    && typeof candidate.retryable === 'boolean'
    && Array.isArray(candidate.next_actions)
    && candidate.next_actions.every(isHostNextAction);
}

/** Normalizes host failures without leaking arbitrary exception objects. */
export function toHostError(value: unknown): DesktopHostError {
  if (value instanceof DesktopHostError) return value;
  if (isHostErrorShape(value)) {
    return new DesktopHostError(
      value.code,
      value.message,
      value.request_id,
      value.retryable,
      value.next_actions,
    );
  }
  return new DesktopHostError(
    'host_bridge_unavailable',
    'Desktop host bridge failed.',
    null,
    false,
    [],
  );
}
