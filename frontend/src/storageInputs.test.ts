import {describe, expect, it} from 'vitest';
import {clearStorageInput, selectStorageInput, storageInputPath} from './storageInputs';
import {copyFragment, pasteFragment} from './editing';
import type {Catalog, DataSource, Graph} from './types';

const catalog: Catalog = {schema_version: 1, operators: [], readers: [
  {id: 'CSVReader', extensions: ['.csv'], contracts: {output: null},
    parameters: [{key: 'companion', label: 'Companion', type: 'string', path_kind: 'source'}]},
]};
const previous: DataSource = {reader: 'CSVReader', path: 'old.csv', dims: ['cells', 'genes'],
  labels: {cells: 'auto', genes: 'builtin'}, args: {companion: 'old-extra.csv', delimiter: ','},
  location: {kind: 'ssh', profile_id: 'old-host'}};
const ref = {storage_id: 'data #1', relative_path: '资料/100% #.csv', version: 'selected-v1', digest: null};

describe('saved configured file selections', () => {
  it('uses a versioned storage URI with existing reader parameters and clears obsolete location/companions', () => {
    const source = selectStorageInput(previous, ref, catalog);
    expect(source.path).toBe('storage://data%20%231/%E8%B5%84%E6%96%99/100%25%20%23.csv');
    expect(source.path).toBe(storageInputPath(ref));
    expect(source.storage_ref).toEqual({...ref, format: 'operon.storage-input', schema_version: 1});
    expect(source.location).toBeUndefined();
    expect(source.args).toEqual({delimiter: ','});
    expect(source.dims).toEqual(previous.dims);
    expect(previous.args.companion).toBe('old-extra.csv');
    expect(previous.location?.kind).toBe('ssh');
  });
  it('requires a fresh stat version and switches back without keeping the storage identity', () => {
    expect(() => selectStorageInput(previous, {...ref, version: null}, catalog)).toThrow();
    const source = selectStorageInput(previous, ref, catalog);
    expect(clearStorageInput(source).storage_ref).toBeUndefined();
    expect(source.storage_ref?.version).toBe('selected-v1');
  });
  it('preserves the saved version and URI when pasting into another document directory', () => {
    const source = selectStorageInput(previous, ref, catalog);
    const graph: Graph = {schema_version: 2, name: 'source', base_dir: '/old', memory: {enabled: true}, edges: [],
      nodes: [{id: 'input', kind: 'source', title: '', position: {x: 0, y: 0}, params: {}, input_count: 1, source}]};
    const fragment = copyFragment(graph, ['input']);
    const result = pasteFragment({...graph, base_dir: '/new', nodes: []}, fragment);
    expect(result.graph.nodes[0].source?.path).toBe(source.path);
    expect(result.graph.nodes[0].source?.storage_ref).toEqual(source.storage_ref);
  });
});
