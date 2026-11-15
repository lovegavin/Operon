import type { DesktopHost } from './types';
import { DesktopHostError } from './types';

/**
 * Browser-safe host: every desktop capability is explicitly unavailable, and
 * ready/close subscription are harmless no-ops.
 */
export function createBrowserHost(): DesktopHost {
  return {
    kind: 'browser',
    async ready() {
      // No desktop host exists to notify.
    },
    async acknowledgeDraftFlush(requestId) {
      throw new DesktopHostError(
        'host_request_stale',
        'No desktop close request is pending in a browser.',
        requestId,
      );
    },
    async showDiagnostics() {
      throw new DesktopHostError(
        'host_capability_unavailable',
        'Host diagnostics are unavailable in a browser.',
        null,
        false,
        ['open_host_logs'],
      );
    },
    async requestFullExit() {
      throw new DesktopHostError(
        'host_capability_unavailable',
        'Full exit through the host is unavailable in a browser.',
        null,
        false,
        ['use_tray_menu_exit'],
      );
    },
    async openCommittedArtifact() {
      throw new DesktopHostError(
        'host_capability_unavailable',
        'Opening a committed artifact through the host is unavailable in a browser.',
        null,
        false,
        ['use_http_artifact_link'],
      );
    },
    onPrepareClose() {
      return () => {
        // No host can request a close in a browser.
      };
    },
  };
}
