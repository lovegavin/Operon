import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {LargeResourceSection, ResourceCard, missingFiles, officialRoot, resourceState} from './LargeResourceSection';
import type {LargeResource} from './types';

function resource(overrides: Partial<LargeResource> = {}): LargeResource {
  return {
    id: 'alphafold2',
    title: 'AlphaFold-2 databases',
    kind: 'database',
    present: false,
    status: 'partial',
    missing: ['uniref90/uniref90.fasta'],
    expected_files: ['params/params_model_1_ptm.npz', 'uniref90/uniref90.fasta'],
    official_root: 'afdb',
    link_roots: ['/public/home/lihj/operon-resources'],
    environments: ['openfold'],
    used_by: ['openfold_predict'],
    size_bytes: 2048,
    ...overrides,
  } as LargeResource;
}

describe('resource cards', () => {
  it('uses the state reported by the API and falls back to the legacy flags', () => {
    expect(resourceState(resource({state: 'linked'}))).toBe('linked');
    expect(resourceState(resource({state: undefined, linked: true} as Partial<LargeResource>))).toBe('linked');
    expect(resourceState(resource({state: undefined, status: 'ok'}))).toBe('downloaded');
    expect(resourceState(resource({state: undefined, status: 'partial'}))).toBe('partial');
    expect(resourceState(resource({state: undefined, status: 'missing'}))).toBe('missing');
  });

  it('names the official directory users have to link', () => {
    expect(officialRoot(resource())).toBe('afdb');
    expect(officialRoot(resource({official_root: undefined} as Partial<LargeResource>))).toBe('alphafold2');
    expect(missingFiles(resource())).toEqual(['uniref90/uniref90.fasta']);
  });

  it('renders a card with the official directory and the missing count', () => {
    const html = renderToStaticMarkup(
      <ResourceCard resource={resource()} onOpen={() => {}} onLink={() => {}}/>,
    );
    expect(html).toContain('afdb');
    expect(html).toContain('缺少 1 个文件');
    expect(html).toContain('查看缺失项');
  });

  it('renders the section shell while loading', () => {
    const html = renderToStaticMarkup(
      <LargeResourceSection target="" targets={[]} onTarget={() => {}}/>,
    );
    expect(html).toContain('大型资源与模型权重');
    expect(html).toContain('正在读取大型资源');
  });
});
