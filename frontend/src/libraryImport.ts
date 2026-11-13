import type {LibraryInstallResult, PluginOperation, PluginState} from './types';

/**
 * Operon Studio 5.0.0 rejects the pre-5.0 library ZIPs. The backend returns
 * HTTP 400 with `detail` set to the literal two-line message; keep the match
 * narrow so ordinary failures still use the generic error path.
 */
const LEGACY_LIBRARY_FORMAT = /legacy\s+8\.x\s+format/i;

export function isLegacyLibraryError(message: string, status?: number) {
  if (!LEGACY_LIBRARY_FORMAT.test(message)) return false;
  return status === undefined || status === 400;
}

export type LibraryInstallSummary = {version: string; packages: number; descriptors: number};

/**
 * Prefer the counts carried by the finished operation (`result`), then fall
 * back to `GET /api/plugins`, so the panel still reports numbers if an older
 * server only records the release.
 */
export function libraryInstallSummary(result: PluginOperation['result'], state?: PluginState): LibraryInstallSummary | null {
  const record = result && typeof result === 'object' ? result as Partial<LibraryInstallResult> : null;
  const version = typeof record?.library_version === 'string' && record.library_version.trim()
    ? record.library_version.trim()
    : state?.library_release?.version || '';
  if (!version) return null;
  const packages = typeof record?.packages === 'number' ? record.packages : state?.packages.length ?? 0;
  const descriptors = typeof record?.descriptors === 'number' ? record.descriptors : state?.descriptors.length ?? 0;
  return {version, packages, descriptors};
}

/** The library entry point accepts wheels as well as library bundles; anything else is a bundle. */
export function isLibraryBundleFile(name: string) {
  return !name.trim().toLowerCase().endsWith('.whl');
}

/** `operon-routes-<name>-v<version>.zip`, and the legacy `operon-routes-v<version>.zip`. */
export function isRouteLibraryFile(name: string) {
  const lower = name.trim().toLowerCase();
  return lower.startsWith('operon-routes-') && lower.endsWith('.zip') && !lower.endsWith('.operon.zip');
}

/** A plain container ZIP (route archive), as opposed to a single `.operon.zip` bundle. */
export function isRouteArchiveFile(name: string) {
  const lower = name.trim().toLowerCase();
  return lower.endsWith('.zip') && !lower.endsWith('.operon.zip');
}

/** Number of changed plugin files reported by a refresh operation. */
export function refreshedCount(result: PluginOperation['result']) {
  return result && 'updated' in result && Array.isArray(result.updated) ? result.updated.length : 0;
}
