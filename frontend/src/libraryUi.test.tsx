import {afterEach, describe, expect, it} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {LegacyLibraryAlert, LibrarySetupGuide} from './LibraryNotices';
import {PluginPanel} from './PluginPanel';
import {setLanguage} from './i18n';

const LEGACY = 'This library bundle uses the legacy 8.x format.\nInstall an operon-library-v0.0.x bundle built for Operon 5.0.0.';

afterEach(() => setLanguage('system'));

describe('empty operator library', () => {
  it('explains the two-ZIP order and downloads nothing automatically', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<LibrarySetupGuide onImport={() => {}}/>);
    expect(html).toContain('No operator library installed');
    expect(html).toContain('Import the operator library bundle first, then the route library bundle.');
    expect(html).toContain('operon-library-v0.0.0.operon-library.zip');
    expect(html).toContain('operon-routes-v0.0.0.zip');
    expect(html).toContain('Import operator library');
    expect(html).toContain('Nothing is downloaded automatically.');
  });

  it('renders inside the library panel when no packages are installed', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<PluginPanel initialTab="manage" onClose={() => {}} onChanged={async () => {}}/>);
    expect(html).toContain('No operator library installed');
    expect(html).toContain('operon-library-v0.0.0.operon-library.zip');
    expect(html).toContain('operon-routes-v0.0.0.zip');
  });
});

describe('route library entry', () => {
  it('offers Import route library next to the single-route import', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<PluginPanel initialTab="add" onClose={() => {}} onChanged={async () => {}}/>);
    expect(html).toContain('Import workflow file');
    expect(html).toContain('Import route library');
    expect(html).toContain('Route library bundle: operon-routes-v0.0.0.zip');
    expect(html).toContain('accept=".zip"');
    expect(html).toContain('Library name');
    expect(html).toContain('Library name (optional, e.g. fork-v0.0.0)');
  });
});

describe('legacy 8.x rejection', () => {
  it('shows the backend message verbatim with the 5.0.0 hint', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<LegacyLibraryAlert message={LEGACY} onChoose={() => {}}/>);
    expect(html).toContain('Legacy 8.x operator library cannot be imported');
    expect(html).toContain('This library bundle uses the legacy 8.x format.');
    expect(html).toContain('Install an operon-library-v0.0.x bundle built for Operon 5.0.0.');
    expect(html).toContain('Operon Studio 5.1.0 only accepts the new operon-library-v0.0.x bundle.');
    expect(html).toContain('Choose operator library bundle');
  });

  it('keeps the Chinese wording available', () => {
    setLanguage('zh-CN');
    const html = renderToStaticMarkup(<LegacyLibraryAlert message={LEGACY} onChoose={() => {}}/>);
    expect(html).toContain('无法导入旧版 8.x 算子库');
    expect(html).toContain('Operon Studio 5.1.0 仅接受新版 operon-library-v0.0.x 算子库包。');
  });
});
