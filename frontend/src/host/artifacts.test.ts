import {describe, expect, it, vi} from 'vitest';
import {createBrowserHost} from './browser';
import {DesktopHostError} from './types';
import {openNativeArtifact} from './artifacts';

describe('native artifact result routing', () => {
  const ids = {run: 'run-1', artifact: 'artifact-1', file: 'file-1'};
  it('passes opaque IDs to the host without downloading in the renderer', async () => {
    const open = vi.fn().mockResolvedValue(undefined);
    const save = vi.fn();
    await openNativeArtifact({...createBrowserHost(), kind: 'tauri', openCommittedArtifact: open}, ids, save);
    expect(open).toHaveBeenCalledWith(ids.run, ids.artifact, ids.file);
    expect(save).not.toHaveBeenCalled();
  });
  it('retains save-as for an explicitly unsupported file association', async () => {
    const error = new DesktopHostError('host_capability_unavailable', 'Unavailable', null, false, ['use_http_artifact_link']);
    const open = vi.fn().mockRejectedValue(error);
    const save = vi.fn().mockResolvedValue(undefined);
    await openNativeArtifact({...createBrowserHost(), openCommittedArtifact: open}, ids, save);
    expect(save).toHaveBeenCalledOnce();
  });
  it('does not bypass a failed integrity or transport check', async () => {
    const error = new DesktopHostError('host_bridge_unavailable', 'Failed');
    const save = vi.fn();
    await expect(openNativeArtifact({...createBrowserHost(), openCommittedArtifact: vi.fn().mockRejectedValue(error)}, ids, save)).rejects.toBe(error);
    expect(save).not.toHaveBeenCalled();
  });
});
