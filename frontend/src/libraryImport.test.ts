import {describe, expect, it} from 'vitest';
import {
  isLegacyLibraryError, isLibraryBundleFile, isRouteArchiveFile, isRouteLibraryFile,
  libraryInstallSummary, refreshedCount,
} from './libraryImport';

const LEGACY = 'This library bundle uses the legacy 8.x format.\nInstall an operon-library-v0.0.x bundle built for Operon 5.0.0.';

describe('library bundle classification', () => {
  it('recognises the 5.0.0 library and route collection names', () => {
    expect(isLibraryBundleFile('operon-library-v0.0.0.operon-library.zip')).toBe(true);
    expect(isLibraryBundleFile('operon-library-v0.0.0.operon-library.zip'.toUpperCase())).toBe(true);
    expect(isLibraryBundleFile('some_operator-1.2.0-py3-none-any.whl')).toBe(false);
    expect(isRouteLibraryFile('operon-routes-v0.0.0.zip')).toBe(true);
    expect(isRouteLibraryFile('operon-routes-main-v0.1.0.zip')).toBe(true);
    expect(isRouteLibraryFile('operon-routes-fork1-v0.0.0.zip')).toBe(true);
    expect(isRouteLibraryFile('routes.zip')).toBe(false);
    expect(isRouteLibraryFile('route.operon.zip')).toBe(false);
    expect(isRouteArchiveFile('routes.zip')).toBe(true);
    expect(isRouteArchiveFile('route.operon.zip')).toBe(false);
  });
});

describe('legacy 8.x detection', () => {
  it('matches the literal backend message on HTTP 400', () => {
    expect(isLegacyLibraryError(LEGACY, 400)).toBe(true);
    expect(isLegacyLibraryError(LEGACY)).toBe(true);
  });

  it('keeps unrelated failures on the generic path', () => {
    expect(isLegacyLibraryError(LEGACY, 500)).toBe(false);
    expect(isLegacyLibraryError('算子库安装失败', 400)).toBe(false);
    expect(isLegacyLibraryError('')).toBe(false);
  });
});

describe('install summaries', () => {
  const state = {
    generation: 'g', packages: [{name: 'a', version: '1', sha256: ''}, {name: 'b', version: '1', sha256: ''}],
    descriptors: [{id: 'a', kind: 'operator' as const, title: 'A', distribution: 'a'}],
    library_release: {version: '0.0.0', sha256: 'x'},
  };

  it('reads counts from the operation result', () => {
    expect(libraryInstallSummary({library_version: '0.0.0', packages: 12, descriptors: 30, installed: true}, state))
      .toEqual({version: '0.0.0', packages: 12, descriptors: 30});
  });

  it('falls back to the refreshed plugin state', () => {
    expect(libraryInstallSummary(undefined, state as never)).toEqual({version: '0.0.0', packages: 2, descriptors: 1});
    expect(libraryInstallSummary({updated: [], unchanged: [], generation: 'g', directory: '', operators: 0, readers: 0}, state as never))
      .toEqual({version: '0.0.0', packages: 2, descriptors: 1});
  });

  it('reports nothing when no library is recorded', () => {
    expect(libraryInstallSummary(undefined, {generation: 'g', packages: [], descriptors: []} as never)).toBeNull();
  });

  it('counts refreshed files only for refresh results', () => {
    expect(refreshedCount({updated: ['a.whl', 'b.whl'], unchanged: [], generation: 'g', directory: '', operators: 0, readers: 0})).toBe(2);
    expect(refreshedCount({library_version: '0.0.0', packages: 1, descriptors: 1, installed: true})).toBe(0);
    expect(refreshedCount(undefined)).toBe(0);
  });
});
