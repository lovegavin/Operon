import {toHostError, type DesktopHost} from './types';

/** Unsupported file types may be saved through the existing HTTP path; a
 * transport or integrity failure must remain visible rather than silently
 * bypassing the native verification boundary. */
export async function openNativeArtifact(
  host: DesktopHost,
  ids: {run: string; artifact: string; file: string},
  saveFallback: () => Promise<void>,
): Promise<void> {
  try {
    await host.openCommittedArtifact(ids.run, ids.artifact, ids.file);
  } catch (failure) {
    const error = toHostError(failure);
    if (error.code === 'host_capability_unavailable' && error.next_actions.includes('use_http_artifact_link')) {
      await saveFallback();
      return;
    }
    throw error;
  }
}
