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
    expect(html).toContain('A new Operon Studio installation contains no operators. Import the operator library bundle first, then the route library.');
    expect(html).toContain('Operator library: .operon-library.zip');
    expect(html).toContain('Route library: .zip');
    expect(html).toContain('Import operator library');
    expect(html).toContain('Nothing is downloaded automatically.');
  });

  it('renders inside the library panel when no packages are installed', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<PluginPanel initialTab="manage" onClose={() => {}} onChanged={async () => {}}/>);
    expect(html).toContain('No operator library installed');
    expect(html).toContain('Operator library: .operon-library.zip');
    expect(html).toContain('Route library: .zip');
  });
});

describe('route library entry', () => {
  it('offers Import route library next to the single-route import', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<PluginPanel initialTab="add" onClose={() => {}} onChanged={async () => {}}/>);
    expect(html).toContain('Import workflow file');
    expect(html).toContain('Import route library');
    expect(html).toContain('Route library: .zip collection');
    expect(html).toContain('accept=".zip"');
  });
});

describe('legacy 8.x rejection', () => {
  it('shows the backend message verbatim with the 5.0.0 hint', () => {
    setLanguage('en');
    const html = renderToStaticMarkup(<LegacyLibraryAlert message={LEGACY} onChoose={() => {}}/>);
    expect(html).toContain('Legacy 8.x operator library cannot be imported');
    expect(html).toContain('This library bundle uses the legacy 8.x format.');
    expect(html).toContain('Install an operon-library-v0.0.x bundle built for Operon 5.0.0.');
    expect(html).toContain('This application only accepts the current operator library bundle (.operon-library.zip).');
    expect(html).toContain('Choose operator library bundle');
  });

  it('keeps the Chinese wording available', () => {
    setLanguage('zh-CN');
    const html = renderToStaticMarkup(<LegacyLibraryAlert message={LEGACY} onChoose={() => {}}/>);
    expect(html).toContain('无法导入旧版 8.x 算子库');
    expect(html).toContain('当前应用仅接受新版算子库包（.operon-library.zip）。');
  });
});
