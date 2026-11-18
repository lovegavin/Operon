import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {LargeResources, linkCandidates, missingEnvironments} from './LargeResources';
import type {LargeResource} from './types';

function resource(overrides: Partial<LargeResource> & {id: string}): LargeResource {
  return {name: overrides.id, ...overrides} as LargeResource;
}

describe('the link dialog options', () => {
  it('keeps only environments that are not ready yet', () => {
    const environments = [
      {name: 'openfold', status: 'missing', title: 'OpenFold (AlphaFold-2)'},
      {name: 'esmfold', status: 'ready', title: 'ESMFold'},
      {name: 'boltz', status: 'failed', title: 'Boltz'},
      {name: 'colabfold', status: 'queued', title: 'ColabFold'},
    ];
    expect(missingEnvironments(environments).map(option => option.name))
      .toEqual(['openfold', 'boltz', 'colabfold']);
  });

  it('offers a missing resource of the chosen environment that can be linked', () => {
    const resources = [
      resource({id: 'alphafold2', link_roots: ['/public/links'], environments: ['openfold'], present: false}),
      resource({id: 'esm2', link_roots: ['/cache'], environments: ['esmfold'], present: false}),
      resource({id: 'pfam', link_roots: [], environments: ['openfold'], present: false}),
      resource({id: 'proteinmpnn', link_roots: ['/ext'], environments: ['openfold'], present: true}),
    ];
    expect(linkCandidates(resources, 'openfold').map(item => item.id)).toEqual(['alphafold2']);
    expect(linkCandidates(resources, '').map(item => item.id)).toEqual(['alphafold2', 'esm2']);
    expect(linkCandidates(resources, '', 'proteinmpnn').map(item => item.id))
      .toEqual(['alphafold2', 'esm2', 'proteinmpnn']);
    expect(linkCandidates(resources, 'esmfold').map(item => item.id)).toEqual(['esm2']);
  });

  it('renders the resource list with the heading and an empty note', () => {
    const html = renderToStaticMarkup(<LargeResources/>);
    expect(html).toContain('大型资源与模型权重');
    expect(html).toContain('正在读取资源…');
  });
});
