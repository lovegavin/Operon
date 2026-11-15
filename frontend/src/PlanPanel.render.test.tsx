import {renderToStaticMarkup} from 'react-dom/server';
import {afterEach, expect, it} from 'vitest';
import {PlanPanel, PlanSummary} from './PlanPanel';
import {samplePlan} from './planTestFixtures';
import {setLanguage} from './i18n';
afterEach(() => setLanguage('system'));
it('offers a guided canvas compile form and marks non-local placement experimental', () => {
  setLanguage('en');
  const html = renderToStaticMarkup(<PlanPanel graph={{schema_version: 2, name: 'Research workflow', base_dir: '.', nodes: [], edges: [], memory: {enabled: true}}} onClose={() => {}}/>);
  expect(html).toContain('Research workflow'); expect(html).toContain('Compile snapshot'); expect(html).toContain('Import plan or manifest');
  expect(html).not.toContain('<textarea');
  const plan = samplePlan(); plan.units[0].placement.executor = 'slurm';
  const summary = renderToStaticMarkup(<PlanSummary plan={plan}/>);
  expect(summary).toContain('Experimental'); expect(summary).toContain('Parameter fingerprint'); expect(summary).toContain('scale');
});
