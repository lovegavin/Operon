import {describe, expect, it} from 'vitest';
import {
  componentStateLabel, isReady, officialRoot, resourceComponents, resourcesOf,
} from './LargeResourceSection';
import type {LargeResource} from './types';

const resource: LargeResource = {
  id: 'alphafold2',
  title: 'AlphaFold2 parameters',
  official_root: 'afdb',
  environments: ['alphafold2'],
  state: 'partial',
  components: [
    {name: 'afdb', path: '', mode: 'tree', bytes: 5_384_039_577, state: 'missing'},
  ],
};

describe('large resource cards', () => {
  it('falls back to a single official unit when none is declared', () => {
    const units = resourceComponents({id: 'x', state: 'missing'} as LargeResource);
    expect(units.map(unit => unit.name)).toEqual(['x']);
  });

  it('reads the official root and declared units', () => {
    expect(officialRoot(resource)).toBe('afdb');
    expect(resourceComponents(resource).map(unit => unit.name)).toEqual(['afdb']);
  });

  it('filters resources by environment', () => {
    expect(resourcesOf([resource], 'alphafold2')).toHaveLength(1);
    expect(resourcesOf([resource], 'boltz')).toHaveLength(0);
    expect(resourcesOf([resource])).toHaveLength(1);
  });

  it('labels component states', () => {
    expect(componentStateLabel({name: 'afdb', state: 'present'})).toBe('已就位');
    expect(componentStateLabel({name: 'afdb', state: 'partial'})).toBe('部分就位');
    expect(componentStateLabel({name: 'afdb', state: 'missing'})).toBe('缺失');
    expect(isReady({name: 'afdb', state: 'linked'})).toBe(true);
    expect(isReady({name: 'afdb', state: 'missing'})).toBe(false);
  });
});
