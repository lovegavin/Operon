import {describe, expect, it} from 'vitest';
import {
  componentStateLabel, declaredFiles, downloadButtonLabel, downloadPercent, downloadStartedMessage,
  isReady, missingFiles, officialRoot, pendingDownloads, resourceComponents, resourcesOf, unitAction,
} from './LargeResourceSection';
import type {LargeResource, LargeResourceOperation} from './types';

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

describe('large resource unit actions', () => {
  it('branch 1: downloads only the missing files that have an HTTP source', () => {
    const component = {
      name: 'afdb',
      state: 'partial',
      files: [
        {name: 'a.cif', present: false},
        {name: 'b.cif', present: false},
        {name: 'c.cif', present: true},
      ],
      missing: ['a.cif', 'b.cif'],
      downloadable: ['a.cif', 'b.cif', 'c.cif'],
      download_supported: true,
    };
    expect(pendingDownloads(component)).toEqual(['a.cif', 'b.cif']);
    const action = unitAction(component);
    expect(action.text).toBe('下载缺失文件（2）');
    expect(action.enabled).toBe(true);
    expect(action.reason.length).toBeGreaterThan(0);
  });

  it('branch 2: falls back to rsync when nothing is downloadable', () => {
    const component = {
      name: 'colabfold',
      state: 'missing',
      missing: ['params.tar.zst'],
      downloadable: [],
      download_supported: true,
      rsync: {url: 'rsync://example.org/pdb/'},
    };
    expect(pendingDownloads(component)).toEqual([]);
    const action = unitAction(component);
    expect(action.text).toBe('rsync 拉取');
    expect(action.enabled).toBe(true);
    expect(action.reason.length).toBeGreaterThan(0);
  });

  it('branch 3: reports no download source when the backend says so', () => {
    const component = {
      name: 'amrfinder',
      state: 'missing',
      files: [{name: 'AMRFinderPlus', present: false}],
      missing: ['AMRFinderPlus'],
      downloadable: [],
      download_supported: false,
      rsync: null,
    };
    const action = unitAction(component);
    expect(action.text).toBe('无下载源');
    expect(action.enabled).toBe(false);
    expect(action.reason.length).toBeGreaterThan(0);
  });

  it('branch 4: reports all ready when nothing is missing', () => {
    const component = {
      name: 'prodigal',
      state: 'present',
      files: [{name: 'prodigal', present: true}],
      missing: [],
      downloadable: ['prodigal'],
      download_supported: true,
    };
    const action = unitAction(component);
    expect(action.text).toBe('已全部就绪');
    expect(action.enabled).toBe(false);
    expect(action.reason.length).toBeGreaterThan(0);
  });

  it('branch 5: reports missing files without any download source', () => {
    const component = {
      name: 'pfam',
      state: 'partial',
      files: [
        {name: 'Pfam-A.hmm', present: false},
        {name: 'Pfam-A.hmm.h3f', present: false},
        {name: 'Pfam-A.hmm.dat', present: false},
      ],
      missing: ['Pfam-A.hmm', 'Pfam-A.hmm.h3f', 'Pfam-A.hmm.dat'],
      downloadable: [],
      download_supported: true,
    };
    const action = unitAction(component);
    expect(action.text).toBe('缺 3 个文件，没有下载源');
    expect(action.enabled).toBe(false);
    expect(action.reason.length).toBeGreaterThan(0);
  });

  it('keeps pending empty when every declared file is already present', () => {
    // 回归：missing 为空时不得把 downloadable 整个当成待下载。
    const component = {
      name: 'rfam',
      state: 'present',
      files: [
        {name: 'Rfam.cm', present: true},
        {name: 'Rfam.cm.i1f', present: true},
      ],
      missing: [],
      downloadable: ['Rfam.cm', 'Rfam.cm.i1f', 'Rfam.cm.i1i'],
      download_supported: true,
    };
    expect(missingFiles(component)).toEqual([]);
    expect(pendingDownloads(component)).toEqual([]);
    expect(unitAction(component).text).toBe('已全部就绪');
  });

  it('does not treat downloadable as pending when the missing field is absent', () => {
    // 后端没给 missing 时退回 files 的 present，取不到就当作空。
    const allPresent = {
      name: 'legacy',
      state: 'present',
      files: [{name: 'data.bin', present: true}],
      downloadable: ['data.bin', 'other.bin'],
    };
    expect(missingFiles(allPresent)).toEqual([]);
    expect(pendingDownloads(allPresent)).toEqual([]);
    expect(unitAction(allPresent).text).toBe('已全部就绪');

    const oneMissing = {
      name: 'legacy2',
      state: 'partial',
      files: [
        {name: 'data.bin', present: false},
        {name: 'other.bin', present: true},
      ],
      downloadable: ['data.bin', 'other.bin'],
    };
    expect(missingFiles(oneMissing)).toEqual(['data.bin']);
    expect(pendingDownloads(oneMissing)).toEqual(['data.bin']);
  });

  it('treats a unit with no declared file manifest as undeclared', () => {
    const component = {name: 'colabfold', state: 'unknown'};
    expect(declaredFiles(component)).toEqual([]);
    expect(componentStateLabel(component)).toBe('未声明文件清单');
  });

  it('never reports an undeclared unit as all ready', () => {
    // colabfold 类：没有任何声明清单，但 download_supported 为真。
    const component = {name: 'colabfold', state: 'unknown', download_supported: true};
    const action = unitAction(component);
    expect(action.text).toBe('未声明文件清单');
    expect(action.enabled).toBe(false);
    expect(action.reason).toBe('该资源没有登记应校验的文件，因此不参与就绪判定');
  });

  it('counts unit-level declared names when component.files is absent', () => {
    // 后端只回填 files_present/files_missing 时，仍要算出「已声明」条目。
    const component = {
      name: 'prodigal',
      state: 'partial',
      files_present: [],
      files_missing: ['prodigal'],
      downloadable: ['prodigal'],
      download_supported: true,
    };
    expect(declaredFiles(component)).toEqual(['prodigal']);
    expect(unitAction(component).text).toBe('下载缺失文件（1）');
  });
});

describe('large resource download feedback', () => {
  it('announces the started unit and its file count immediately', () => {
    expect(downloadStartedMessage('afdb', 3)).toBe('已开始下载 afdb（3 个文件）');
  });

  it('turns declared byte progress into a percentage', () => {
    expect(downloadPercent({id: 'job', status: 'running', completed_bytes: 25, planned_bytes: 200}))
      .toBe(12);
    expect(downloadPercent({id: 'job', status: 'running', completed_bytes: 400, planned_bytes: 200}))
      .toBe(100);
    expect(downloadPercent({id: 'job', status: 'running'})).toBe(0);
  });

  it('labels the button while running, after success and after failure', () => {
    const running: LargeResourceOperation = {
      id: 'job', status: 'running', completed_bytes: 50, planned_bytes: 200,
    };
    expect(downloadButtonLabel(running, '下载缺失文件（2）')).toBe('下载中 25%');
    expect(downloadButtonLabel({id: 'job', status: 'running'}, '下载缺失文件（2）'))
      .toBe('下载中…（等待字节统计）');
    // planned_bytes == 0 但已有已写字节：显示已下载量而不是 0%。
    expect(downloadButtonLabel({id: 'job', status: 'running', percent: null,
      planned_bytes: 0, downloaded_bytes: 2_621_440}, '下载缺失文件（2）'))
      .toBe('下载中（已下载 2.5 MB）');
    expect(downloadButtonLabel({id: 'job', status: 'running', indeterminate: true,
      downloaded_bytes: 1_536}, '下载缺失文件（2）')).toBe('下载中（已下载 1536 B）');
    expect(downloadButtonLabel({id: 'job', status: 'succeeded'}, '下载缺失文件（2）'))
      .toBe('下载完成');
    expect(downloadButtonLabel({id: 'job', status: 'failed', error: '磁盘已满'}, '下载缺失文件（2）'))
      .toBe('磁盘已满');
    expect(downloadButtonLabel(undefined, '下载缺失文件（2）')).toBe('下载缺失文件（2）');
  });

  it('shows a cancelled job in Chinese and re-enables the action', () => {
    expect(downloadButtonLabel({id: 'job', status: 'cancelled', error: 'cancelled'},
      '下载缺失文件（2）')).toBe('已取消');
  });

  it('clips a failed job error to 200 characters', () => {
    const long = 'x'.repeat(300);
    expect(downloadButtonLabel({id: 'job', status: 'failed', error: long},
      '下载缺失文件（2）')).toHaveLength(200);
  });
});
