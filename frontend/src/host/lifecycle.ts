import type { DesktopHost } from './types';
import { toHostError } from './types';

/** Same flush body used by the desktop close handshake. */
export type CloseFlush = () => unknown;
export type CloseErrorHandler = (error: ReturnType<typeof toHostError>) => void;

/**
 * Register the single close listener before the caller announces readiness.
 * The returned cleanup suppresses every late ACK and unsubscribes once.
 */
export function connectCloseHandshake(
  host: DesktopHost,
  flush: CloseFlush,
  onError: CloseErrorHandler = () => {},
): () => void {
  let active = true;

  const report = (value: unknown) => {
    if (!active) return;
    onError(toHostError(value));
  };

  const acknowledge = (requestId: string, saved: boolean) => {
    if (!active) return;
    let pending: Promise<void>;
    try {
      pending = host.acknowledgeDraftFlush(requestId, saved);
    } catch (error) {
      report(error);
      return;
    }
    // One ACK attempt only: a failed ACK is reported once and never retried
    // as a negative ACK.
    void Promise.resolve(pending).catch((error) => report(error));
  };

  const handlePrepareClose = (requestId: string) => {
    if (!active) return;

    let result: unknown;
    try {
      result = flush();
    } catch {
      acknowledge(requestId, false);
      return;
    }

    void Promise.resolve(result).then(
      () => acknowledge(requestId, true),
      () => acknowledge(requestId, false),
    );
  };

  const unsubscribe = host.onPrepareClose(handlePrepareClose);

  return () => {
    if (!active) return;
    active = false;
    unsubscribe();
  };
}
