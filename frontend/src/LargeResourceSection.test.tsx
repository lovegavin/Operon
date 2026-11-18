import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {LargeResourceSection, ResourceRow, groupResources, resourceState, unitState} from './LargeResourceSection';
import type {LargeResource} from './types';

function item(patch: Partial<LargeResource> = {}): LargeResource {
  return {id: 'openfold', title: 'OpenFold', status: 'missing', ...patch} as LargeResource;
}

describe('large resource section', () => {
  it('trusts the reported state and falls back to presence flags', () => {
    expect(resourceState(item({state: 'linked'}))).toBe('linked');
    expect(resourceState(item({state: 'downloaded'}))).toBe('downloaded');
    expect(resourceState(item({linked: true}))).toBe('linked');
    expect(resourceState(item({status: 'ok'}))).toBe('downloaded');
    expect(resourceState(item({status: 'partial'}))).toBe('partial');
    expect(resourceState(item())).toBe('missing');
  });

  it('reads the unit state from the server and then from the receipt flag', () => {
    expect(unitState({name: 'params', state: 'linked'})).toBe('linked');
    expect(unitState({name: 'params', receipt: true})).toBe('downloaded');
    expect(unitState({name: 'params'})).toBe('missing');
  });

  it('groups resources by environment and keeps unowned ones last', () => {
    const groups = groupResources([
      item({id: 'proteinmpnn', environments: []}),
      item({id: 'openfold', environments: ['openfold']}),
      item({id: 'esm2', environments: ['esm2', 'esm3']}),
    ]);
    expect(groups.map(group => group.environment)).toEqual(['esm2', 'esm3', 'openfold', '']);
    expect(groups[2].items.map(resource => resource.id)).toEqual(['openfold']);
  });

  it('renders the environment heading and both link affordances', () => {
    const tree = renderToStaticMarkup(<ResourceRow resource={item({id: 'af2', title: 'AlphaFold-2'})}
      busy={false} onLink={() => {}} onUnlink={() => {}}/>);
    expect(tree).toContain('AlphaFold-2');
    expect(tree).toContain('链接已有目录');

    const units = renderToStaticMarkup(<ResourceRow busy={false} onLink={() => {}} onUnlink={() => {}}
      resource={item({id: 'esm2', link_unit: 'items', units: [
        {name: 'esm2_t6_8M_UR50D.pt', state: 'missing'},
        {name: 'esm2_t12_35M_UR50D.pt', state: 'linked', target: '/data/esm'},
      ]})}/>);
    expect(units).toContain('esm2_t6_8M_UR50D.pt');
    expect(units).toContain('esm2_t12_35M_UR50D.pt');
    expect(units).toContain('解除');
  });

  it('renders the execution location selector before any resource loads', () => {
    const tree = renderToStaticMarkup(<LargeResourceSection target="" targets={[]} onTarget={() => {}}/>);
    expect(tree).toContain('执行位置');
    expect(tree).toContain('大型资源与模型权重');
    expect(tree).toContain('正在读取大型资源…');
  });
});
