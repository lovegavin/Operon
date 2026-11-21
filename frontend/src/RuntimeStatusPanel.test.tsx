import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';

import {
  EnvironmentCard,
  LogDrawer,
  OperationList,
  SummaryStrip,
  availableActions,
  formatBytes,
  formatElapsed,
  phaseLabel,
  purposeOf,
  readinessLabels,
  readinessOf,
  reasonText,
  resourceProgress,
  shortId,
  statusTone,
  summarize,
  usedByText,
  type EnvironmentItem,
  type EnvironmentOperation,
} from './RuntimeStatusPanel';

const NOW = Date.parse('2026-01-01T00:00:00Z');
const noop = () => {};

function item(overrides: Partial<EnvironmentItem> = {}): EnvironmentItem {
  return {
    name: 'openmm81',
    python: '3.11',
    spec_sha256: 'a'.repeat(64),
    interpreter: '/envs/openmm81/bin/python',
    location: '/envs/openmm81',
    imports: [],
    status: 'missing',
    error: '',
    used_by: [],
    progress: null,
    ...overrides,
  };
}

function operation(overrides: Partial<EnvironmentOperation> = {}): EnvironmentOperation {
  return {
    id: '0123456789abcdef0123456789abcdef',
    name: 'openmm81',
    status: 'running',
    error: '',
    started_at: '2026-01-01T00:00:00Z',
    finished_at: null,
    ...overrides,
  };
}

function card(overrides: Partial<EnvironmentItem> = {}) {
  return renderToStaticMarkup(<EnvironmentCard item={item(overrides)}/>);
}

describe('status mapping', () => {
  it('maps stored and job statuses onto the five chip tones', () => {
    expect(statusTone('ready')).toBe('ready');
    expect(statusTone('complete')).toBe('ready');
    expect(statusTone('stale')).toBe('stale');
    expect(statusTone('incomplete')).toBe('stale');
    expect(statusTone('installing')).toBe('installing');
    expect(statusTone('running')).toBe('installing');
    expect(statusTone('failed')).toBe('failed');
    expect(statusTone('missing')).toBe('missing');
    expect(statusTone('cancelled')).toBe('missing');
    expect(statusTone('queued')).toBe('queued');
    expect(statusTone('something-new')).toBe('missing');
  });

  it('counts each tone for the summary strip', () => {
    const counts = summarize([
      item({name: 'a', status: 'ready'}),
      item({name: 'b', status: 'ready'}),
      item({name: 'c', status: 'missing'}),
      item({name: 'd', status: 'installing'}),
      item({name: 'e', status: 'failed'}),
      item({name: 'f', status: 'queued'}),
    ]);
    expect(counts).toEqual(
      {total: 6, ready: 2, missing: 1, queued: 1, stale: 0, installing: 1, failed: 1});
  });
});

describe('action availability', () => {
  it('offers prepare only when the environment is missing', () => {
    expect(availableActions('missing')).toEqual(['prepare', 'log']);
  });

  it('offers repair for stale and failed environments', () => {
    expect(availableActions('stale')).toEqual(['repair', 'log']);
    expect(availableActions('failed')).toEqual(['repair', 'log']);
    expect(availableActions('incomplete')).toEqual(['repair', 'log']);
  });

  it('allows cancel only while installing and keeps logs reachable', () => {
    expect(availableActions('installing')).toEqual(['log', 'cancel']);
    expect(availableActions('queued')).toEqual(['log', 'cancel']);
    expect(availableActions('ready')).toEqual(['log']);
    expect(availableActions('ready', 2)).toEqual(['optional', 'log']);
    expect(availableActions('cancelled')).toEqual(['prepare', 'log']);
  });
});

describe('progress rendering', () => {
  it('renders phase and transferred size for an installing card', () => {
    const html = card({status: 'installing', progress: {phase: 'installing', bytes: 300 * 1024 * 1024}});
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('runtime-progress-fill');
    expect(html).toContain('安装依赖 · 300 MB');
    expect(html).toContain('class="runtime-chip is-installing"');
  });

  it('hides the progress bar once an environment is ready', () => {
    expect(card({status: 'ready'})).not.toContain('progressbar');
  });

  it('falls back to a generic label before the first progress frame', () => {
    expect(card({status: 'installing'})).toContain('正在安装…');
  });
});

describe('summary strip', () => {
  it('shows totals and only the non-zero tones', () => {
    const items = [
      item({name: 'a', status: 'ready'}),
      item({name: 'b', status: 'ready'}),
      item({name: 'c', status: 'missing'}),
      item({name: 'd', status: 'installing'}),
      item({name: 'e', status: 'queued'}),
    ];
    const html = renderToStaticMarkup(<SummaryStrip items={items} busy={false} onPrepareAll={noop} onRefresh={noop}/>);
    expect(html).toContain('5 个环境');
    expect(html).toContain('2 已就绪');
    expect(html).toContain('1 未安装');
    expect(html).toContain('1 正在安装');
    expect(html).toContain('1 准备安装');
    expect(html).not.toContain('需要更新');
    expect(html).toContain('全部安装');
    expect(html).toContain('刷新');
  });

  it('disables prepare-all when nothing needs work and while busy', () => {
    const ready = [item({status: 'ready'})];
    const idle = renderToStaticMarkup(<SummaryStrip items={ready} busy={false} onPrepareAll={noop} onRefresh={noop}/>);
    expect(idle.match(/disabled=""/g)?.length).toBe(1);
    const busy = renderToStaticMarkup(<SummaryStrip items={[item({status: 'missing'})]} busy={true} onPrepareAll={noop} onRefresh={noop}/>);
    expect(busy.match(/disabled=""/g)?.length).toBe(2);
  });
});

describe('readiness groups', () => {
  it('maps each stored status onto one label and never reuses a label', () => {
    const labels = Object.values(readinessLabels());
    expect(new Set(labels).size).toBe(labels.length);
    expect(readinessOf(item({status: 'ready'}))).toBe('ready');
    expect(readinessOf(item({status: 'incomplete', dependency_total: 8, dependency_installed: 8})))
      .toBe('resource-gap');
    expect(readinessOf(item({status: 'incomplete', dependency_total: 15, dependency_installed: 14})))
      .toBe('dependency-gap');
    expect(readinessOf(item({status: 'stale', progress: {phase: 'failed'}}))).toBe('interrupted');
    expect(readinessOf(item({status: 'stale'}))).toBe('stale');
    expect(readinessOf(item({status: 'cancelled'}))).toBe('stale');
    expect(readinessOf(item({status: 'missing'}))).toBe('missing');
  });

  it('shows one summary line per distinguishable reason', () => {
    const items = [
      item({name: 'a', status: 'stale', progress: {phase: 'failed'}}),
      item({name: 'b', status: 'stale'}),
      item({name: 'c', status: 'missing'}),
      item({name: 'd', status: 'incomplete', dependency_total: 8, dependency_installed: 8}),
      item({name: 'e', status: 'incomplete', dependency_total: 2, dependency_installed: 1}),
    ];
    const html = renderToStaticMarkup(<SummaryStrip items={items} busy={false} onPrepareAll={noop} onRefresh={noop}/>);
    expect(html).toContain('1 安装已中断');
    expect(html).toContain('1 需重新准备');
    expect(html).toContain('1 未安装');
    expect(html).toContain('1 资源未齐备');
    expect(html).toContain('1 依赖缺失');
    expect(html).not.toContain('未就绪');
  });

  it('counts maintenance units like the resource panel and falls back to the counters', () => {
    expect(resourceProgress(item({resources_total: 0, shared_resources_total: 5, shared_resources_ready: 1})))
      .toEqual({total: 5, ready: 1});
    expect(resourceProgress(item({resources_total: 3, resources_ready: 1}), {total: 3, ready: 0}))
      .toEqual({total: 3, ready: 0});
    expect(resourceProgress(item({resources_total: 2, resources_ready: 5}))).toEqual({total: 2, ready: 2});
  });

  it('gives a stale or missing card a definite reason', () => {
    expect(reasonText(item({status: 'stale'}), 'stale')).toBe('该环境未安装或安装记录已失效，请重新准备');
    expect(reasonText(item({status: 'missing'}), 'missing')).toBe('该环境未安装或安装记录已失效，请重新准备');
    const stale = card({status: 'stale'});
    expect(stale).toContain('data-testid="environment-reason-openmm81"');
    expect(stale).toContain('该环境未安装或安装记录已失效，请重新准备');
    expect(card({status: 'stale', progress: {phase: 'failed'}})).toContain('安装已中断');
    expect(card({status: 'stale', error: '上次安装已中断（安装进程已退出），请重新准备该环境。'}))
      .toContain('上次安装已中断（安装进程已退出），请重新准备该环境。');
  });

  it('shows the resource shortfall on an incomplete card', () => {
    const html = renderToStaticMarkup(<EnvironmentCard
      item={item({status: 'incomplete', dependency_total: 3, dependency_installed: 3})}
      gap={{total: 3, ready: 1, missing: ['antismash', 'antismash']}}/>);
    expect(html).toContain('data-status="stale"');
    expect(html).toContain('data-readiness="resource-gap"');
    expect(html).toContain('资源 1/3');
    expect(html).toContain('资源未齐备');
    expect(html).toContain('title="缺失资源：antismash"');
    expect(html).not.toContain('安装失败');
  });
});

describe('operations', () => {
  it('lists only running operations with elapsed time and a cancel action', () => {
    const html = renderToStaticMarkup(<OperationList now={NOW + 5000} operations={[
      operation(),
      operation({id: 'done', name: 'boltz', status: 'complete'}),
    ]}/>);
    expect(html).toContain('进行中的操作');
    expect(html).toContain('openmm81');
    expect(html).toContain('5s');
    expect(html).toContain('取消');
    expect(html).not.toContain('boltz');
    expect(html).toContain('01234567…');
  });

  it('hides cancel for operations the server no longer allows cancelling', () => {
    const html = renderToStaticMarkup(<OperationList operations={[operation({cancelable: false})]}/>);
    expect(html).not.toContain('取消');
  });

  it('renders nothing when no operation is running', () => {
    const html = renderToStaticMarkup(<OperationList operations={[operation({status: 'complete'})]}/>);
    expect(html).toBe('');
  });
});

describe('log drawer', () => {
  it('shows the inline tail returned by the API', () => {
    const html = renderToStaticMarkup(
      <LogDrawer name="openmm81" text={'collecting\ninstalling torch'} pending={false} error="" onClose={noop} onRefresh={noop}/>,
    );
    expect(html).toContain('openmm81 的日志');
    expect(html).toContain('installing torch');
    expect(html).toContain('environment-log');
    expect(html).toContain('关闭');
  });

  it('covers pending, empty and error states', () => {
    expect(renderToStaticMarkup(<LogDrawer name="x" text="" pending={true} error="" onClose={noop} onRefresh={noop}/>))
      .toContain('正在读取日志…');
    expect(renderToStaticMarkup(<LogDrawer name="x" text="" pending={false} error="" onClose={noop} onRefresh={noop}/>))
      .toContain('暂无日志');
    expect(renderToStaticMarkup(<LogDrawer name="x" text="" pending={false} error="boom" onClose={noop} onRefresh={noop}/>))
      .toContain('boom');
  });
});

describe('formatting helpers', () => {
  it('formats byte sizes without noisy decimals', () => {
    expect(formatBytes(0)).toBe('—');
    expect(formatBytes(-4)).toBe('—');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(1536)).toBe('1.5 KB');
    expect(formatBytes(300 * 1024 * 1024)).toBe('300 MB');
    expect(formatBytes(1024 ** 3)).toBe('1 GB');
  });

  it('formats elapsed time at second, minute and hour scale', () => {
    expect(formatElapsed(null)).toBe('—');
    expect(formatElapsed('not-a-date')).toBe('—');
    expect(formatElapsed('2026-01-01T00:00:00Z', NOW + 5000)).toBe('5s');
    expect(formatElapsed('2026-01-01T00:00:00Z', NOW + 65000)).toBe('1m 5s');
    expect(formatElapsed('2026-01-01T00:00:00Z', NOW + 3700000)).toBe('1h 1m');
  });

  it('renders the used-by count with the number substituted', () => {
    const markup = renderToStaticMarkup(<EnvironmentCard
      item={item({used_by: ['a', 'b'], used_by_count: 2})} />);
    expect(markup).toContain('2 个算子');
    expect(markup).not.toContain('{n}');
  });

  it('summarises the used-by list as three names plus a count', () => {
    expect(usedByText(item())).toBe('无');
    expect(usedByText(item({used_by: ['a', 'b'], used_by_count: 2}))).toBe('a · b');
    expect(usedByText(item({used_by: ['a', 'b', 'c'], used_by_count: 9}))).toBe('a · b · c +6');
  });

  it('takes the first sentence of the manifest notes and shortens long ids', () => {
    expect(purposeOf(item({notes: '\n 第一行 \n第二行'}))).toBe('第一行');
    expect(purposeOf(item({notes: ''}))).toBe('');
    expect(shortId('0123456789abcdef')).toBe('01234567…');
    expect(shortId('abc')).toBe('abc');
  });

  it('translates known phases and falls back for unknown ones', () => {
    expect(phaseLabel('installing')).toBe('安装依赖');
    expect(phaseLabel('probing')).toBe('校验导入');
    expect(phaseLabel(undefined)).toBe('准备中');
    expect(phaseLabel('mystery')).toBe('准备中');
  });
});
