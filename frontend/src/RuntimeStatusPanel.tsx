import {useEffect, useState} from 'react';
import {Modal} from './RouteDialogs';
import {t} from './i18n';
import {api} from './api';
import {isReady, LargeResourceSection, resourceComponents} from './LargeResourceSection';
import type {
  EnvironmentJob, EnvironmentSnapshot, PoolStatus, RemoteEnvironments, StudioVersion,
} from './api';
import type {LargeResource} from './types';

export type EnvironmentItem = EnvironmentSnapshot['environments'][string] & {
  title?: string;
  notes?: string;
  size_bytes?: number;
  interpreter?: string;
  python_version?: string;
  updated_at?: string;
  operator_count?: number;
  operators?: string[];
  planned?: boolean;
  used_by_count?: number;
  expected_bytes?: number;
  queue_position?: number;
  error?: string;
  resources?: string[];
  dependencies?: Array<{kind: string; name: string; installed?: boolean; version?: string}>;
  dependency_total?: number;
  resources_total?: number;
  resources_ready?: number;
  resources_missing?: string[];
  shared_resources_total?: number;
  shared_resources_ready?: number;
  missing_dependencies?: string[];
  optional_missing?: string[];
  optional_total?: number;
  supported?: boolean;
  platform_note?: string;
  dependency_installed?: number;
  shared?: boolean;
  managed?: boolean;
};
export type EnvironmentOperation = EnvironmentJob & {cancelable?: boolean};
export type EnvironmentView = Omit<EnvironmentSnapshot, 'environments' | 'operations'> & {
  environments: Record<string, EnvironmentItem>;
  operations: EnvironmentOperation[];
};

export type Tone = 'ready' | 'missing' | 'queued' | 'stale' | 'installing' | 'failed';
export type Action = 'prepare' | 'repair' | 'optional' | 'log' | 'cancel';

const tones: Tone[] = ['ready', 'missing', 'queued', 'stale', 'installing', 'failed'];

/** Status chips share this mapping: green ready, grey missing, amber stale, blue installing, red failed. */
export function statusTone(status: string): Tone {
  switch (status) {
    case 'ready':
    case 'complete':
      return 'ready';
    case 'queued':
      return 'queued';
    case 'incomplete':
    case 'stale':
      return 'stale';
    case 'installing':
    case 'running':
      return 'installing';
    case 'failed':
      return 'failed';
    default:
      return 'missing';
  }
}

/**
 * Status labels keyed by the stored status, never by the colour tone: one tone
 * covers several statuses, and a colour is not a reason.
 */
const statusKeys: Record<string, string> = {
  ready: '已就绪',
  complete: '已就绪',
  incomplete: '资源未齐备',
  stale: '需重新准备',
  missing: '未安装',
  failed: '安装失败',
  queued: '准备安装',
  installing: '正在安装',
  running: '正在安装',
};

/**
 * Readiness groups. Each group owns one label and no two groups may share it:
 * the summary strip and the card chip are read as the same text, so a reused
 * label would merge two different reasons into one line.
 */
export type Readiness = 'ready' | 'resource-gap' | 'dependency-gap' | 'interrupted'
  | 'stale' | 'missing' | 'failed' | 'queued' | 'installing';

const readinessKeys: Record<Readiness, string> = {
  ready: '已就绪',
  'resource-gap': '资源未齐备',
  'dependency-gap': '依赖缺失',
  interrupted: '安装已中断',
  stale: '需重新准备',
  missing: '未安装',
  failed: '安装失败',
  queued: '准备安装',
  installing: '正在安装',
};

const readinessTones: Record<Readiness, Tone> = {
  ready: 'ready',
  'resource-gap': 'stale',
  'dependency-gap': 'failed',
  interrupted: 'failed',
  stale: 'stale',
  missing: 'missing',
  failed: 'failed',
  queued: 'queued',
  installing: 'installing',
};

/**
 * Maintenance units of one environment, counted the way the resource panel
 * counts its cards: one per component, ready only when present or linked.
 * `gap` comes from the same /resources payload the panel renders, so the unit
 * count and "ready/total" cannot disagree with the cards. The backend counters
 * are a fallback for snapshots that arrive without that payload (older remote
 * servers, or a failed fetch); `shared_resources_*` covers an environment whose
 * units are declared outside the manifest, where `resources_total` stays 0.
 */
export function resourceProgress(item: EnvironmentItem, gap?: {total: number; ready: number}) {
  if (gap && gap.total > 0) return {total: gap.total, ready: Math.min(gap.ready, gap.total)};
  const declared = Number(item.resources_total || 0);
  const total = declared || Number(item.shared_resources_total || 0);
  const ready = declared ? Number(item.resources_ready || 0)
    : Number(item.shared_resources_ready || 0);
  return {total, ready: Math.min(ready, total)};
}

/**
 * Readiness is decided by the stored status first and by measured dependencies
 * and resources second. `error` is deliberately not part of the test: a
 * resource shortfall also writes `error` (environment_api.snapshot), and keying
 * on it turned every incomplete environment into "安装失败".
 */
export function readinessOf(item: EnvironmentItem, gap?: {total: number; ready: number}): Readiness {
  const status = String(item.status || '').toLowerCase();
  const tone = statusTone(status);
  if (tone === 'queued') return 'queued';
  if (tone === 'installing') return 'installing';
  if (status === 'missing') return 'missing';
  if (status === 'failed' || tone === 'failed') return 'failed';
  if (status === 'cancelled') return 'stale';
  if (status === 'stale') {
    return String(item.progress?.phase || '').toLowerCase() === 'failed' ? 'interrupted' : 'stale';
  }
  const total = Number(item.dependency_total || 0);
  const installed = Number(item.dependency_installed || 0);
  const missingDependencies = total > 0 && installed < total;
  if (status === 'incomplete') return missingDependencies ? 'dependency-gap' : 'resource-gap';
  if (missingDependencies) return 'dependency-gap';
  const progress = resourceProgress(item, gap);
  if (progress.total > 0 && progress.ready < progress.total) return 'resource-gap';
  if (!item.interpreter) return 'stale';
  return 'ready';
}

export function readinessLabels() {
  return readinessKeys;
}

export function readinessCounts(items: EnvironmentItem[], gaps: Record<string, {total: number; ready: number}> = {}) {
  const counts: Record<Readiness, number> = {
    ready: 0, 'resource-gap': 0, 'dependency-gap': 0, interrupted: 0,
    stale: 0, missing: 0, failed: 0, queued: 0, installing: 0,
  };
  for (const item of items) counts[readinessOf(item, gaps[item.name])] += 1;
  return counts;
}

export function statusLabelKey(status: string) {
  return statusKeys[String(status || '').toLowerCase()] || readinessKeys.missing;
}

const phaseKeys: Record<string, string> = {
  queued: '准备安装',
  creating: '创建环境',
  installing: '安装依赖',
  probing: '校验导入',
  committing: '提交环境',
  ready: '已就绪',
  failed: '安装失败',
};

export function phaseLabel(phase?: string) {
  if (!phase) return t('准备中');
  return t(phaseKeys[phase] || '准备中');
}

export function availableActions(status: string, optionalMissing = 0): Action[] {
  const actions: Action[] = [];
  if (status === 'missing' || status === 'cancelled') actions.push('prepare');
  if (status === 'stale' || status === 'failed' || status === 'incomplete') actions.push('repair');
  // Optional bindings (pyarrow, pysam, vina ...) never block readiness, so a ready
  // environment with a failed optional install needs its own entry point.
  if (status === 'ready' && optionalMissing > 0) actions.push('optional');
  actions.push('log');
  if (statusTone(status) === 'installing' || statusTone(status) === 'queued') actions.push('cancel');
  return actions;
}

export function summarize(items: EnvironmentItem[]) {
  const counts = {total: items.length, ready: 0, missing: 0, queued: 0, stale: 0, installing: 0, failed: 0};
  for (const item of items) {
    const tone = statusTone(item.status);
    if (tone === 'missing') counts.missing += 1;
    else counts[tone] += 1;
  }
  return counts;
}

export function formatBytes(bytes?: number) {
  if (!bytes || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const rounded = value >= 10 ? value.toFixed(0) : value.toFixed(1);
  return `${rounded.replace(/\.0$/, '')} ${units[index]}`;
}

export function sizeText(item: EnvironmentItem) {
  const tone = statusTone(item.status);
  if (tone === 'ready' || tone === 'stale') return formatBytes(item.size_bytes);
  const received = item.progress?.bytes || 0;
  if (tone === 'installing' && received > 0) return `${t('安装中')} · ${formatBytes(received)}`;
  return t('未安装');
}

export function usageCount(item: EnvironmentItem) {
  return item.operator_count ?? item.used_by_count ?? (item.used_by || []).length;
}

export function queueText(item: EnvironmentItem) {
  return item.queue_position ? t('队列第 {n} 位', {n: item.queue_position}) : '';
}

export function failureText(item: EnvironmentItem) {
  const reason = (item.error || item.progress?.error || '').trim();
  if (!reason) return '';
  return reason.length > 180 ? `${reason.slice(0, 177)}…` : reason;
}

/**
 * A definite reason for the card. Stale and missing environments carry an empty
 * `error` on the wire (environment_install.state clears it for stale, and an
 * uninstalled environment never had one), so every branch ends in a sentence
 * instead of a blank line.
 */
export function reasonText(item: EnvironmentItem, readiness?: Readiness): string {
  const explicit = failureText(item);
  if (explicit) return explicit;
  const status = String(item.status || '').toLowerCase();
  if (item.planned && status === 'missing') return '';
  if (readiness === 'interrupted') return t('安装已中断');
  if (readiness === 'dependency-gap') return t('该环境的依赖安装未完成');
  if (readiness === 'resource-gap') return t('资源未齐备');
  if (readiness === 'stale' || readiness === 'missing') {
    if (item.supported === false) return item.platform_note || t('当前系统不支持');
    return t('该环境未安装或安装记录已失效，请重新准备');
  }
  return '';
}

export function percentDone(item: EnvironmentItem) {
  const expected = item.expected_bytes || 0;
  const received = item.progress?.bytes || 0;
  if (!expected || received <= 0) return 0;
  const raw = Math.round((received / expected) * 100);
  // The byte counter only covers downloads; dependency installation continues
  // afterwards. Keep the real number: a settled download renders as an
  // indeterminate bar with the phase label instead of a fake 99%.
  return Math.max(1, Math.min(raw, 100));
}

export function formatElapsed(start?: string | null, now: number = Date.now()) {
  if (!start) return '—';
  const from = Date.parse(start);
  if (!Number.isFinite(from)) return '—';
  const seconds = Math.max(0, Math.round((now - from) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

/** The manifest `notes` field is prose; the card shows one sentence of it. */
export function purposeOf(item: EnvironmentItem) {
  const notes = (item.notes || '').trim();
  if (!notes) return '';
  const line = notes.split('\n').map(part => part.trim()).find(Boolean) || '';
  return line.length > 160 ? `${line.slice(0, 157)}…` : line;
}

export function shortId(id?: string) {
  if (!id) return '';
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

export function operatorsOf(item: EnvironmentItem) {
  return item.operators || item.used_by || [];
}

export function usedByText(item: EnvironmentItem) {
  const names = operatorsOf(item);
  const total = usageCount(item);
  if (!total) return t('无');
  const head = names.slice(0, 3);
  const suffix = total > head.length ? ` +${total - head.length}` : '';
  return `${head.join(' · ')}${suffix}`;
}

export function actionLabel(action: Action) {
  return t({prepare: '准备', repair: '修复', optional: '补装可选依赖', log: '查看日志', cancel: '取消'}[action]);
}

function progressText(item: EnvironmentItem) {
  const phase = item.progress?.phase;
  const size = formatBytes(item.progress?.bytes);
  const label = phase ? phaseLabel(phase) : t('正在安装…');
  return size === '—' ? label : `${label} · ${size}`;
}

export function SummaryStrip({items, gaps = {}, busy, target = '', targets = [], onTarget,
  onPrepareAll, onRefresh}: {
  items: EnvironmentItem[];
  gaps?: Record<string, {total: number; ready: number}>;
  busy: boolean;
  target?: string;
  targets?: Array<{id: string; name: string}>;
  onTarget?: (id: string) => void;
  onPrepareAll: () => void;
  onRefresh: () => void;
}) {
  const counts = summarize(items);
  const readiness = readinessCounts(items, gaps);
  const pending = counts.missing + counts.stale + counts.failed;
  return <div className="runtime-summary">
    <div className="runtime-summary-counts" aria-live="polite" aria-label={t('环境概况')}>
      <strong>{t('{count} 个环境', {count: counts.total})}</strong>
      {(Object.keys(readiness) as Readiness[]).filter(key => readiness[key] > 0).map(key =>
        <span className="runtime-summary-item" data-readiness={key} key={key}>
          <i className="runtime-dot" aria-hidden="true"/>
          {t('{count} {label}', {count: readiness[key], label: t(readinessKeys[key])})}
        </span>)}
    </div>
    <div className="runtime-summary-actions">
      {onTarget && <label className="runtime-target">
        <span>{t('执行位置')}</span>
        <select value={target} disabled={busy} onChange={event => onTarget(event.target.value)}>
          <option value="">{t('本地')}</option>
          {targets.map(remote => <option key={remote.id} value={remote.id}>{remote.name}</option>)}
        </select>
      </label>}
      <button className="subtle-button" disabled={busy} onClick={onRefresh}>{t('刷新')}</button>
      <button className="primary-button" disabled={busy || pending === 0} onClick={onPrepareAll}>{t('全部安装')}</button>
    </div>
  </div>;
}

export function EnvironmentCard({item, busy = false, cancelling = false, gap, onAction, onOpen}: {
  item: EnvironmentItem;
  busy?: boolean;
  cancelling?: boolean;
  gap?: {total: number; ready: number; missing: string[]};
  onAction?: (action: Action, name: string) => void;
  onOpen?: (item: EnvironmentItem) => void;
}) {
  const tone = statusTone(item.status);
  const readiness = readinessOf(item, gap);
  const progress = resourceProgress(item, gap);
  const reason = reasonText(item, readiness);
  const installing = tone === 'installing';
  const settling = installing && percentDone(item) >= 99;
  const waiting = installing && (item.progress?.bytes || 0) <= 0;
  return <article className="runtime-card is-openable" data-status={tone} data-testid={`environment-${item.name}`}
    role="button" tabIndex={0}
    onClick={(event) => {
      if ((event.target as HTMLElement).closest('button, summary, a, input, select')) return;
      onOpen?.(item);
    }}
    onKeyDown={(event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      onOpen?.(item);
    }}>
    <header className="runtime-card-head">
      <div className="runtime-card-title">
        <h3>{item.name}</h3>
        <code>{item.title || item.name}</code>
      </div>
      <div className="runtime-card-tags">
        {item.planned && <span className="runtime-badge">{t('预留')}</span>}
        {item.supported === false && <span className="runtime-chip is-warning" title={item.platform_note}>
          {t('当前系统不支持')}
        </span>}
        {queueText(item) && <span className="runtime-queue">{queueText(item)}</span>}
        <span className={`runtime-chip is-${readinessTones[readiness]}`} data-status={tone} data-readiness={readiness}>{t(readinessKeys[readiness])}</span>
        {readiness === 'resource-gap' && progress.total > 0 && <span
          className="runtime-chip is-warning"
          data-testid={`environment-resources-${item.name}`}
          title={`${t('缺失资源：')}${[...new Set(gap?.missing || [])].join('、')}`}>
          {t('资源 {ready}/{total}', {ready: progress.ready, total: progress.total})}
        </span>}
      </div>
    </header>
    <p className="runtime-purpose" title={item.notes || undefined}>
      {purposeOf(item) || t('暂无说明')}
    </p>
    {installing && <div className="runtime-progress-block">
      <div className={`runtime-progress${settling || waiting ? ' is-indeterminate' : ''}`} role="progressbar"
        aria-label={t('安装进度')} aria-valuetext={progressText(item)} aria-valuemin={0}
        aria-valuemax={100} aria-valuenow={settling || waiting ? undefined : percentDone(item)}>
        <span className="runtime-progress-fill" style={{width: settling || waiting ? '100%' : `${percentDone(item)}%`}}/>
      </div>
      <small className="runtime-progress-label">{settling
        ? `${progressText(item)} · ${t('已用 {time}', { time: formatElapsed(item.progress?.started_at) })}`
        : waiting ? `${progressText(item)} · ${t('已用 {time}', { time: formatElapsed(item.progress?.started_at) })}`
        : item.expected_bytes ? `${percentDone(item)}% · ${progressText(item)}` : progressText(item)}</small>
    </div>}
    <dl className="runtime-facts">
      <div><dt>{t('Python 版本')}</dt><dd>{item.python_version || item.python || '—'}</dd></div>
      <div><dt>{t('占用空间')}</dt><dd>{sizeText(item)}</dd></div>
      <div className="runtime-facts-usage"><dt>{t('使用算子')}</dt>
        {usageCount(item) ? <details className="runtime-usedby">
          <summary>{t('{n} 个算子', {n: usageCount(item)})}</summary>
          <ul>{operatorsOf(item).map(name => <li key={name}><code>{name}</code></li>)}</ul>
        </details> : <dd>{item.planned ? t('预留环境（无内置算子）') : t('无')}</dd>}
      </div>
    </dl>
    {reason && <p className="runtime-error" title={reason} data-testid={`environment-reason-${item.name}`}>
      {readiness === 'failed' ? `${t('安装失败')}：` : ''}{reason}
    </p>}
    <footer className="runtime-actions">
      {availableActions(item.status, (item.optional_missing || []).length).map(action =>
        <button key={action}
          className={`subtle-button${action === 'prepare' || action === 'repair' || action === 'optional' ? ' is-primary' : ''}${action === 'cancel' ? ' is-danger' : ''}`}
          disabled={busy || (action === 'cancel' && cancelling)
            || (item.supported === false && (action === 'prepare' || action === 'repair' || action === 'optional'))}
          title={item.supported === false && (action === 'prepare' || action === 'repair' || action === 'optional') ? item.platform_note : undefined}
          onClick={() => onAction?.(action, item.name)}>
          {action === 'cancel' && cancelling ? t('取消中…') : actionLabel(action)}
        </button>)}
    </footer>
  </article>;
}

export function OperationList({operations, now = Date.now(), onCancel}: {
  operations: EnvironmentOperation[];
  now?: number;
  onCancel?: (name: string) => void;
}) {
  const running = operations.filter(operation => operation.status === 'running');
  if (!running.length) return null;
  return <section className="runtime-operations" aria-label={t('进行中的操作')}>
    <h3>{t('进行中的操作')}</h3>
    {running.map(operation => <div className="runtime-operation" key={operation.id}
      data-testid={`operation-${operation.id}`}>
      <strong>{operation.name}</strong>
      <code title={operation.id}>{shortId(operation.id)}</code>
      <span className="runtime-op-phase">{phaseLabel(operation.phase)}</span>
      <span className="runtime-op-elapsed">{formatElapsed(operation.started_at, now)}</span>
      {operation.cancelable !== false &&
        <button className="subtle-button is-danger" onClick={() => onCancel?.(operation.name)}>{t('取消')}</button>}
    </div>)}
    <small className="runtime-background-note">
      {t('安装与下载在后台运行，关闭窗口不会中断。')}
    </small>
  </section>;
}

export function LogDrawer({name, text, pending, error, onClose, onRefresh}: {
  name: string;
  text: string;
  pending: boolean;
  error: string;
  onClose: () => void;
  onRefresh: () => void;
}) {
  return <section className="runtime-log-drawer" aria-label={t('操作日志')}>
    <header>
      <h3>{t('{name} 的日志', {name})}</h3>
      <div className="runtime-actions">
        <button className="subtle-button" disabled={pending} onClick={onRefresh}>{t('刷新')}</button>
        <button className="subtle-button" onClick={onClose}>{t('关闭')}</button>
      </div>
    </header>
    {error && <p className="runtime-warning">{error}</p>}
    <pre className="environment-log">{pending ? t('正在读取日志…') : text || t('暂无日志')}</pre>
  </section>;
}

export function RuntimeStatusPanel({onClose}: {onClose: () => void}) {
  const [snapshot, setSnapshot] = useState<EnvironmentView | null>(null);
  const [pool, setPool] = useState<PoolStatus | null>(null);
  const [appVersion, setAppVersion] = useState<StudioVersion | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [poolBusy, setPoolBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [log, setLog] = useState<{name: string; text: string; error: string} | null>(null);
  const [logPending, setLogPending] = useState(false);
  const [remoteLoaded, setRemoteLoaded] = useState<Record<string, RemoteEnvironments>>({});
  const [remoteBusy, setRemoteBusy] = useState('');
  const [remoteError, setRemoteError] = useState('');
  // The panel always opens on the local target: a remembered remote target used
  // to come back while the remote snapshot was unreachable, which rendered as
  // connected with an empty environment list. The choice lasts while the panel is
  // open.
  const [target, setTarget] = useState<string>('');
  const [remotePending, setRemotePending] = useState(false);
  const [resourceList, setResourceList] = useState<LargeResource[]>([]);
  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const answer = target ? await api.remoteResources(target) : await api.largeResources();
        const rows = ((answer as unknown as { resources?: LargeResource[] }).resources) || [];
        if (alive) setResourceList(rows.filter(row => Boolean(row && row.id)));
      } catch {
        /* readiness falls back to the backend counters below */
      }
    })();
    return () => { alive = false; };
  }, [target]);
  // Counted exactly like the resource panel counts its cards (one per component,
  // ready = present or linked), so badge, detail entry card and panel header can
  // never report different numbers for the same environment.
  const resourceGap = (() => {
    const result: Record<string, {total: number; ready: number; missing: string[]}> = {};
    for (const resource of resourceList) {
      const owners = Array.isArray(resource.environments) ? resource.environments : [];
      if (!owners.length) continue;
      const components = resourceComponents(resource);
      const ready = components.filter(isReady).length;
      for (const owner of owners) {
        const entry = result[owner] || {total: 0, ready: 0, missing: []};
        entry.total += components.length;
        entry.ready += ready;
        if (ready < components.length && !entry.missing.includes(resource.id)) entry.missing.push(resource.id);
        result[owner] = entry;
      }
    }
    return result;
  })();
  const [detail, setDetail] = useState<EnvironmentItem | null>(null);
  // One row per dependency name: the wire list can carry the same name twice
  // (openmm81 declares "wheel" twice), which used to render two identical cards
  // and two identical keys.
  const dependencyRows = (() => {
    const seen = new Set<string>();
    return (detail?.dependencies || []).filter(entry => {
      const name = String(entry.name || '').trim();
      const key = name.toLowerCase();
      if (!name || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  })();
  const dependencyTotal = dependencyRows.length;
  const dependencyInstalled = dependencyRows.filter(entry => entry.installed).length;
  const detailUnits = detail ? resourceProgress(detail, resourceGap[detail.name]) : {total: 0, ready: 0};
  const unitTotal = detailUnits.total;
  const [view, setView] = useState<'root' | 'deps' | 'resources'>('root');
  const [cancelling, setCancelling] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [nextPool, nextSnapshot, nextVersion] = await Promise.all([
          api.pool(),
          api.environments(),
          api.version().catch(() => null),
        ]);
        if (!active) return;
        setPool(nextPool);
        setSnapshot(nextSnapshot as unknown as EnvironmentView);
        setAppVersion(nextVersion);
        setError('');
      } catch (failure) {
        if (active) setError((failure as Error).message);
      }
    }
    load();
    const timer = window.setInterval(load, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!target) return;
    let active = true;
    async function loadRemote() {
      setRemotePending(true);
      try {
        const value = await api.remoteEnvironments(target as string);
        if (!active) return;
        setRemoteLoaded(current => ({...current, [target as string]: value}));
        setRemoteError('');
      } catch (failure) {
        if (active) setRemoteError((failure as Error).message);
      } finally {
        if (active) setRemotePending(false);
      }
    }
    void loadRemote();
    const timer = window.setInterval(loadRemote, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [target]);

  const byName = (left: {name?: string}, right: {name?: string}) =>
    String(left.name || '').localeCompare(String(right.name || ''));
  const localItems = Object.values(snapshot?.environments || {}).sort(byName);
  const remoteItems = Object.values(remoteLoaded[target]?.environments || {}).sort(byName);
  const localByName = new Map(localItems.map(item => [String(item.name || ''), item]));
  // Strict machine isolation: a remote target is rendered from the remote
  // snapshot alone. Only static catalogue labels are attached afterwards, and
  // never any field that describes local runtime state (dependencies, resource
  // units, interpreter, location, progress, size).
  const CATALOGUE_FIELDS = ['title', 'notes', 'planned', 'operator_count', 'operators', 'expected_bytes'] as const;
  const merged = target
    ? remoteItems.map(raw => {
        const item = raw as unknown as EnvironmentItem;
        const meta = localByName.get(String(item.name || '')) as Record<string, unknown> | undefined;
        if (!meta) return item;
        const copy: Record<string, unknown> = {...(item as unknown as Record<string, unknown>)};
        for (const field of CATALOGUE_FIELDS) {
          const value = meta[field];
          if (value === undefined || value === null) continue;
          if (typeof value === 'string' && value.trim() === '') continue;
          if (Array.isArray(value) && value.length === 0) continue;
          if (copy[field] === undefined || copy[field] === null || copy[field] === '') copy[field] = value;
        }
        return copy as unknown as EnvironmentItem;
      })
    : localItems;
  const items = merged as unknown as EnvironmentItem[];
  const rank = (item: EnvironmentItem) => {
    const tone = statusTone(item.status);
    return tone === 'installing' ? 0 : tone === 'queued' ? 1 : 2;
  };
  const ordered = [...items].sort((left, right) => {
    const byRank = rank(left) - rank(right);
    if (byRank) return byRank;
    if (rank(left) < 2) return (left.queue_position || 0) - (right.queue_position || 0);
    return String(left.name || '').localeCompare(String(right.name || ''));
  });
  const operations = snapshot?.operations || [];
  const remoteTargets = (pool?.remotes || []).filter(remote => remote.connected)
    .map(remote => ({id: remote.profile.id, name: remote.profile.name}));

  async function run(label: string, work: () => Promise<EnvironmentSnapshot>, done = '') {
    setBusy(label);
    setError('');
    setNotice('');
    try {
      setSnapshot(await work() as unknown as EnvironmentView);
      if (done) setNotice(done);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
    }
  }


  async function runDependency(name: string, kind: string, requirement: string) {
    const label = `dependency:${requirement}`;
    setBusy(label);
    setError('');
    try {
      if (target) {
        await api.remoteEnvironmentDependencyDownload(target, name, kind, requirement);
      } else {
        await api.environmentDependencyDownload(name, kind, requirement);
      }
      setNotice(t('已开始安装「{name}」的依赖 {requirement}；若环境尚未创建会先创建环境，可点「查看日志」跟踪进度。', {name, requirement}));
      setSnapshot(await api.environments() as unknown as EnvironmentView);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function loadLog(name: string) {
    setLog({name, text: '', error: ''});
    setLogPending(true);
    try {
      const value = target
        ? await api.remoteEnvironmentLog(target, name, 400)
        : await api.environmentLog(name, 400);
      setLog({name, text: value.text || t('该环境还没有日志输出。'), error: ''});
    } catch (failure) {
      setLog({name, text: '', error: (failure as Error).message});
    } finally {
      setLogPending(false);
    }
  }

  function act(action: Action, name: string) {
    if (action === 'log') return void loadLog(name);
    if (target) {
      if (action === 'cancel') {
        setCancelling(current => ({...current, [name]: true}));
        void runRemote(`cancel:${name}`, () => api.remoteCancelEnvironment(target, name),
          t('已请求服务器取消「{name}」。', {name}))
          .finally(() => setCancelling(current => ({...current, [name]: false})));
        return;
      }
      if (action === 'optional') {
        return void runRemote(`remote:${name}`,
          () => api.remotePrepareEnvironments(target, [name], false, true),
          t('已向服务器提交补装可选依赖「{name}」。', {name}));
      }
      return void runRemote(`remote:${name}`, () => api.remotePrepareEnvironments(target, [name]),
        t('已向服务器提交安装「{name}」。', {name}));
    }
    if (action === 'prepare') {
      return void run(`prepare:${name}`, () => api.prepareEnvironments([name]),
        t('已开始安装「{name}」，可在卡片上查看进度或点「查看日志」。', {name}));
    }
    if (action === 'repair') {
      if (target) {
        return void runRemote(`repair:${name}`,
          () => api.remoteEnvironmentRetry(target, name) as unknown as Promise<RemoteEnvironments>,
          t('已请求服务器重新安装「{name}」。', {name}));
      }
      return void run(`repair:${name}`, () => api.retryEnvironment(name),
        t('已请求重新安装「{name}」。', {name}));
    }
    setCancelling(current => ({...current, [name]: true}));
    void (async () => {
      setBusy(`cancel:${name}`);
      setError('');
      setNotice('');
      try {
        const value = await api.cancelEnvironment(name) as unknown as {
          completed?: boolean;
          cancelled?: boolean;
          reason?: string;
        };
        if (value && value.completed) {
          setNotice(t('该环境已完成安装，取消无效。'));
        } else if (value && value.cancelled === false && value.reason) {
          setNotice(t(value.reason));
        } else {
          setNotice(t('已请求取消「{name}」。', {name}));
        }
        setSnapshot(await api.environments() as unknown as EnvironmentView);
      } catch (failure) {
        setError((failure as Error).message);
      } finally {
        setBusy('');
        setCancelling(current => ({...current, [name]: false}));
      }
    })();
    return;
  }

  async function runRemote(label: string, work: () => Promise<RemoteEnvironments>, done = '') {
    setBusy(label);
    setError('');
    setRemoteError('');
    setNotice('');
    try {
      const value = await work();
      setRemoteLoaded(current => ({...current, [target]: value}));
      if (done) setNotice(done);
    } catch (failure) {
      setRemoteError((failure as Error).message);
    } finally {
      setBusy('');
    }
  }

  function chooseTarget(id: string) {
    setRemoteError('');
    setTarget(id);
    if (id && !remoteLoaded[id]) void loadRemote(id);
  }

  async function stopPool(force: boolean) {
    if (typeof window !== 'undefined' && !window.confirm(force ? t('确定要强制清除本地共享池吗？') : t('确定要停止本地共享池吗？'))) return;
    setPoolBusy(true);
    setError('');
    try {
      await api.stopPool(force);
      setPool(await api.pool());
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setPoolBusy(false);
    }
  }

  async function stopRemote(id: string, force: boolean) {
    if (typeof window !== 'undefined' && !window.confirm(t('确定要停止远程共享池吗？'))) return;
    setPoolBusy(true);
    setRemoteError('');
    try {
      await api.remotePoolStop(id, force);
      setPool(await api.pool());
    } catch (failure) {
      setRemoteError((failure as Error).message);
    } finally {
      setPoolBusy(false);
    }
  }

  async function loadRemote(id: string) {
    setRemoteBusy(id);
    setRemoteError('');
    try {
      const value = await api.remoteEnvironments(id);
      setRemoteLoaded(current => ({...current, [id]: value}));
    } catch (failure) {
      setRemoteError((failure as Error).message);
    } finally {
      setRemoteBusy('');
    }
  }

  async function prepareRemote(id: string) {
    setRemoteBusy(id);
    setRemoteError('');
    try {
      const value = await api.remotePrepareEnvironments(id);
      setRemoteLoaded(current => ({...current, [id]: value}));
    } catch (failure) {
      setRemoteError((failure as Error).message);
    } finally {
      setRemoteBusy('');
    }
  }

  return <Modal title={t('运行状态')} onClose={onClose}>
    <div className="runtime-panel">
      {error && <pre className="modal-error">{error}</pre>}
      {target && remoteError &&
        <div className="runtime-warning" data-testid="remote-unavailable">
          <strong>{t('远程环境清单读取失败')}</strong>
          <span>{remoteError}</span>
          <button className="subtle-button" disabled={Boolean(remoteBusy)}
            onClick={() => void loadRemote(target)}>{t('重新连接')}</button>
        </div>}
      {!snapshot && !error && <div className="modal-empty"><p>{t('正在读取环境状态…')}</p></div>}
      {snapshot && !snapshot.manifest.present && !target &&
        <div className="modal-empty"><p>{t('当前算子库没有环境清单')}</p></div>}
      {((snapshot && snapshot.manifest.present) || target) && !items.length &&
        <div className="modal-empty">
          <p>{target
            ? remotePending && !remoteError ? t('正在读取远程环境清单…') : t('当前目标没有隔离环境')
            : t('没有隔离环境')}</p>
          {!target && <small>{t('算子库未声明需要独立安装的环境。')}</small>}
        </div>}
      {((snapshot && snapshot.manifest.present) || target) && items.length > 0 &&
        <SummaryStrip items={items} gaps={resourceGap} busy={Boolean(busy)} target={target} targets={remoteTargets}
          onTarget={chooseTarget}
          onRefresh={() => void (target
            ? runRemote('refresh', () => api.remoteEnvironments(target))
            : run('refresh', () => api.environments()))}
          onPrepareAll={() => void (target
            ? runRemote('all', () => api.remotePrepareEnvironments(target))
            : run('all', () => api.prepareEnvironments()))}
          />}
      {target && items.length > 0 && (() => {
        const local = new Set(Object.keys(snapshot?.environments || {}));
        const remote = new Set(items.map(item => item.name));
        const onlyLocal = [...local].filter(name => !remote.has(name)).sort();
        const onlyRemote = [...remote].filter(name => !local.has(name)).sort();
        if (!onlyLocal.length && !onlyRemote.length) return null;
        return <div className="runtime-warning" data-testid="remote-mismatch">
          <strong>{t('远程环境清单与本地不一致')}</strong>
          <span>{t('本地 {local} 个，远程 {remote} 个。', {local: local.size, remote: remote.size})}</span>
          {onlyLocal.length ? <span>{t('只有本地有：')}{onlyLocal.join('、')}</span> : null}
          {onlyRemote.length ? <span>{t('只有远程有：')}{onlyRemote.join('、')}</span> : null}
          <span>{t('本地清单')}：<code>{snapshot?.manifest?.path || '—'}</code></span>
          <span>{t('远程清单')}：<code>{(remoteLoaded[target] as unknown as { manifest?: { path?: string } })?.manifest?.path || '—'}</code></span>
        </div>;
      })()}
      {items.length > 0 && <div className="runtime-grid">
        {ordered.map(item => <EnvironmentCard key={item.name} item={item}
          gap={resourceGap[item.name]}
          busy={Boolean(busy)} cancelling={Boolean(cancelling[item.name])}
          onAction={act} onOpen={setDetail}/>)}
      </div>}
      <OperationList operations={operations} now={now} onCancel={name => act('cancel', name)}/>
      {detail && <Modal title={`${detail.title || detail.name}`}
        onClose={() => { setDetail(null); setView('root'); }}>
        <p className="settings-note">{detail.name} · {t(readinessKeys[readinessOf(detail, resourceGap[detail.name])])}</p>
        {view === 'root' && <div className="resource-unit-grid">
          <button type="button" className="runtime-card resource-entry-card"
            data-testid="detail-dependencies" onClick={() => setView('deps')}>
            <header className="runtime-card-head">
              <div className="runtime-card-title">
                <h3>{t('环境依赖')}</h3>
                <code>{t('{n} 项', {n: dependencyTotal})}</code>
              </div>
              <span className={`runtime-chip is-${dependencyInstalled === dependencyTotal && dependencyTotal > 0 ? 'ready' : 'missing'}`}>
                {t('{done}/{total} 已安装', {done: dependencyInstalled, total: dependencyTotal})}
              </span>
            </header>
            <p className="runtime-purpose">{t('逐个安装依赖，也可以在依赖名片右上角全部安装。')}</p>
          </button>
          {unitTotal > 0 && <button type="button" className="runtime-card resource-entry-card"
            data-testid="detail-resources" onClick={() => setView('resources')}>
            <header className="runtime-card-head">
              <div className="runtime-card-title">
                <h3>{t('资源')}</h3>
                <code>{t('{n} 个维护单元', {n: unitTotal})}</code>
              </div>
              <span className={`runtime-chip is-${detailUnits.ready === unitTotal ? 'ready' : 'warning'}`}
                data-testid="detail-resources-ready">
                {t('资源 {ready}/{total}', {ready: detailUnits.ready, total: unitTotal})}
              </span>
            </header>
            <p className="runtime-purpose">{t('逐个下载或链接官方最小维护单元。')}</p>
          </button>}
        </div>}
        {view === 'deps' && <section className="runtime-detail-block">
          <header className="runtime-resources-header">
            <div><h3>{t('环境依赖')}</h3></div>
            <div className="runtime-resources-actions">
              <button type="button" className="primary-button" disabled={busy === `prepare:${detail.name}`}
                onClick={() => act('prepare', detail.name)}>{t('全部安装')}</button>
            </div>
          </header>
          {dependencyRows.length === 0
            ? <p className="muted">{t('这个环境没有额外依赖。')}</p>
            : <div className="resource-unit-grid">
              {dependencyRows.map((entry) => <article
                key={`${entry.kind}:${entry.name}`}
                className="runtime-card resource-unit-card"
                data-testid={`dependency-${entry.name}`}>
                <header className="runtime-card-head">
                  <div className="runtime-card-title">
                    <h3>{entry.name}</h3>
                    <code>{entry.kind}</code>
                  </div>
                  <span className={`runtime-chip is-${entry.installed === true ? 'ready' : entry.installed === false ? 'missing' : 'unknown'}`}
                    data-testid={`dependency-state-${entry.name}`}>
                    {entry.installed === true ? t('已安装') : entry.installed === false ? t('未安装') : t('状态未知')}
                  </span>
                </header>
                <footer className="runtime-actions">
                  <button type="button" className="subtle-button is-primary"
                    disabled={busy === `dependency:${entry.name}`}
                    onClick={() => void runDependency(detail.name, entry.kind, entry.name)}>
                    {entry.installed ? t('重新安装') : t('安装')}
                  </button>
                </footer>
              </article>)}
            </div>}
        </section>}
        {view === 'resources' && <section className="runtime-detail-block">
          <LargeResourceSection target={target} environment={detail.name} compact/>
        </section>}
        {view !== 'root' && <div className="runtime-detail-footer">
          <button type="button" className="subtle-button"
            onClick={() => setView('root')}>{t('返回')}</button>
        </div>}
      </Modal>}
      {log && <LogDrawer name={log.name} text={log.text} pending={logPending} error={log.error}
        onClose={() => setLog(null)} onRefresh={() => void loadLog(log.name)}/>}
      <details className="runtime-advanced">
        <summary>{t('高级选项')}</summary>
        <section className="runtime-pool">
          <h3>{t('本地共享池')}</h3>
          {pool ? <>
            <p className="muted">
              {t('版本')} {appVersion?.display || appVersion?.version || pool.instance.version || '—'}
              {' · '}PID {pool.instance.pid ?? '—'}
              {' · '}{t('工作区')} {pool.workspaces.length}
              {' · '}{t('运行任务')} {pool.active.length}
            </p>
            {appVersion?.version && pool.instance.version && appVersion.version !== pool.instance.version &&
              <p className="runtime-warning">{t('共享池版本与界面版本不一致。')}</p>}
            <div className="runtime-actions">
              <button className="subtle-button" disabled={poolBusy} onClick={() => void stopPool(false)}>{t('停止共享池')}</button>
              <button className="subtle-button is-danger" disabled={poolBusy} onClick={() => void stopPool(true)}>{t('强制清除共享池')}</button>
            </div>
            {pool.active.length > 0 && <ul className="runtime-jobs">
              {pool.active.map(job => <li key={job.id}>
                <code title={job.id}>{shortId(job.id)}</code>
                <span>{job.title || job.status}</span>
                <span>{job.status}</span>
              </li>)}
            </ul>}
          </> : <p className="muted">{t('尚未连接共享池。')}</p>}
        </section>
        <section className="runtime-remotes">
          <h3>{t('服务器连接')}</h3>
          {!pool?.remotes.length && <p className="muted">{t('没有配置远程服务器。')}</p>}
          {pool?.remotes.map(remote => <div className="runtime-remote" key={remote.profile.id}>
            <header>
              <strong>{remote.profile.name}</strong>
              <span>{remote.connected ? t('已连接') : t('未连接')}</span>
            </header>
            {remote.pool && <p className="muted">
              {t('运行任务')} {remote.pool.active_count ?? 0}
            </p>}
            <div className="runtime-actions">
              {remote.pool && <button className="subtle-button" disabled={poolBusy}
                onClick={() => void stopRemote(remote.profile.id, false)}>{t('停止共享池')}</button>}
              <button className="subtle-button" disabled={remoteBusy === remote.profile.id}
                onClick={() => void loadRemote(remote.profile.id)}>{t('查看远程环境')}</button>
              <button className="subtle-button" disabled={remoteBusy === remote.profile.id}
                onClick={() => void prepareRemote(remote.profile.id)}>{t('准备远程环境')}</button>
            </div>
            {remoteLoaded[remote.profile.id]?.environments &&
              <ul className="runtime-jobs">
                {Object.entries(remoteLoaded[remote.profile.id].environments || {}).map(([name, item]) =>
                  <li key={name}>
                    <code>{name}</code>
                    <span>{item.operator_count ?? item.used_by?.length ? `${item.operator_count ?? item.used_by?.length} ${t('个算子')}` : '—'}</span>
                    <span>{item.status || '—'}</span>
                  </li>)}
              </ul>}
          </div>)}
          {remoteError && <p className="runtime-warning">{remoteError}</p>}
          {notice && <p className="runtime-warning">{notice}</p>}
        </section>
      </details>
    </div>
  </Modal>;
}

export default RuntimeStatusPanel;
