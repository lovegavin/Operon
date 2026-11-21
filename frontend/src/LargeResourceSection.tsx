import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import { Modal } from './RouteDialogs';
import { t } from './i18n';
import type { LargeResource, LargeResourceComponent, LargeResourceOperation } from './types';

export function resourceState(resource: LargeResource): string {
  return String(resource.state || '').toLowerCase();
}

export function resourceStateLabel(state: string): string {
  switch (String(state || '').toLowerCase()) {
    case 'present':
    case 'linked':
      return t('已就位');
    case 'partial':
      return t('部分就位');
    case 'unknown':
      return t('未声明文件清单');
    default:
      return t('缺失');
  }
}

export function officialRoot(resource: LargeResource): string {
  return String(resource.official_root || resource.link_root || resource.id || '');
}

export function resourceComponents(resource: LargeResource): LargeResourceComponent[] {
  const declared = Array.isArray(resource.components) ? resource.components : [];
  if (declared.length) return declared;
  const name = officialRoot(resource);
  if (!name) return [];
  return [{ name, path: '', mode: 'tree', state: resourceState(resource) }];
}

export function resourcesOf(resources: LargeResource[], environment?: string): LargeResource[] {
  if (!environment) return resources;
  return resources.filter((resource) =>
    (resource.environments || []).includes(environment));
}

export function componentStateLabel(component: LargeResourceComponent): string {
  return resourceStateLabel(String(component.state || 'missing'));
}

// 缺失清单只认 component.missing；后端没有该字段时退回 files 里的 present===false，
// 再退回后端按 unit 清单算好的 files_missing。
// 三处都取不到就当作空，绝不把 downloadable 整个当成待下载。
export function missingFiles(component: LargeResourceComponent): string[] {
  if (Array.isArray(component.missing)) {
    return component.missing.map((name) => String(name || '')).filter(Boolean);
  }
  const files = Array.isArray(component.files) ? component.files : [];
  const derived = files.filter((file) => file && file.present === false)
    .map((file) => String(file.name || '')).filter(Boolean);
  if (derived.length) return derived;
  if (Array.isArray(component.files_missing)) {
    return component.files_missing.map((name) => String(name || '')).filter(Boolean);
  }
  return [];
}

// 待下载 = downloadable ∩ missing；missing 为空时结果必为空。
export function pendingDownloads(component: LargeResourceComponent): string[] {
  const missing = missingFiles(component);
  if (!missing.length) return [];
  const downloadable = Array.isArray(component.downloadable) ? component.downloadable : [];
  return downloadable.map((name) => String(name || ''))
    .filter((name) => name && missing.includes(name));
}

// 已登记应校验的文件：files / files_present / files_missing / missing 的并集，
// 用于「已声明 {count} 项」；后端只在 unit 级保留清单时也能数出条目。
export function declaredFiles(component: LargeResourceComponent): string[] {
  const files = Array.isArray(component.files) ? component.files : [];
  const names = files.map((file) => String(file && file.name ? file.name : '')).filter(Boolean);
  const groups = [component.files_present, component.files_missing, missingFiles(component)];
  for (const group of groups) {
    if (!Array.isArray(group)) continue;
    for (const entry of group) {
      const name = String(entry || '');
      if (name && !names.includes(name)) names.push(name);
    }
  }
  return names;
}

export function isReady(component: LargeResourceComponent): boolean {
  const state = String(component.state || '').toLowerCase();
  return state === 'present' || state === 'linked';
}

// 单元卡的动作判定：固定五分支，顺序不可变；取不到的字段一律当作空/未声明。
export function unitAction(component: LargeResourceComponent): {
  text: string; enabled: boolean; reason: string;
} {
  const missing = missingFiles(component);
  const pending = pendingDownloads(component);
  // 1) 有可下载的缺失文件：走 HTTP 下载。
  if (pending.length) {
    return {
      text: t('下载缺失文件（{n}）', { n: pending.length }),
      enabled: true,
      reason: t('只下载缺失的 {n} 个文件，已就绪的文件不会重复下载', { n: pending.length }),
    };
  }
  // 2) 没有可下载的缺失文件，但该单元提供 rsync 源。
  if (component.rsync) {
    return {
      text: t('rsync 拉取'),
      enabled: true,
      reason: t('该单元只提供 rsync 源，点按后用 rsync 拉取到资源根目录'),
    };
  }
  // 3) 后端明确说过该单元没有下载源。
  if (component.download_supported === false) {
    return {
      text: t('无下载源'),
      enabled: false,
      reason: t('该单元没有可用的下载源，请链接已有目录'),
    };
  }
  // 4) 后端没登记应校验的文件：不参与就绪判定，也不能说成「已全部就绪」。
  if (!declaredFiles(component).length) {
    return {
      text: t('未声明文件清单'),
      enabled: false,
      reason: t('该资源没有登记应校验的文件，因此不参与就绪判定'),
    };
  }
  // 5) 没有缺失文件。
  if (!missing.length) {
    return {
      text: t('已全部就绪'),
      enabled: false,
      reason: t('该单元声明的文件都已就位'),
    };
  }
  // 6) 有缺失，但没有 HTTP/rsync 源。
  return {
    text: t('缺 {count} 个文件，没有下载源', { count: missing.length }),
    enabled: false,
    reason: t('{n} 个文件没有下载源，只能链接已有目录。', { n: missing.length }),
  };
}

function megabytes(value?: number): string {
  const bytes = Number(value || 0);
  if (!bytes) return '—';
  if (bytes >= 1024 ** 4) return `${(bytes / 1024 ** 4).toFixed(2)} TB`;
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${bytes} B`;
}

export type DownloadProgress = { job: string; unit: string; operation: LargeResourceOperation };

export function downloadStartedMessage(unit: string, files: number): string {
  return t('已开始下载 {unit}（{n} 个文件）', { unit, n: files });
}

export function downloadPercent(operation?: LargeResourceOperation): number {
  const planned = Number(operation?.planned_bytes || 0);
  if (planned <= 0) return 0;
  const completed = Number(operation?.completed_bytes || 0);
  return Math.max(0, Math.min(100, Math.floor((completed / planned) * 100)));
}

function clippedError(error: unknown, fallback: string): string {
  const text = String(error || fallback);
  return text.length > 200 ? text.slice(0, 200) : text;
}

export function downloadButtonLabel(operation: LargeResourceOperation | undefined,
                                    fallback: string): string {
  if (!operation) return fallback;
  const status = String(operation.status || '').toLowerCase();
  if (status === 'succeeded') return t('下载完成');
  if (status === 'failed') return clippedError(operation.error, t('下载失败'));
  // 后端的取消错误就是字面量 'cancelled'；终态必须显示中文。
  if (status === 'cancelled') return t('已取消');
  if (status === 'running' || status === 'queued') {
    if (Number(operation.planned_bytes || 0) > 0) {
      return t('下载中 {percent}%', { percent: downloadPercent(operation) });
    }
    // planned_bytes == 0 说明清单里不是每个文件都声明了大小（后端因此返回
    // percent: null + indeterminate）；此时显示已写字节数，连字节都还没统计
    // 到时才退回不确定态文案。
    const downloaded = Number(operation.downloaded_bytes || 0);
    if (downloaded > 0) return t('下载中（已下载 {size}）', { size: megabytes(downloaded) });
    return t('下载中…（等待字节统计）');
  }
  return fallback;
}

function operationActive(operation?: LargeResourceOperation): boolean {
  const status = String(operation?.status || '').toLowerCase();
  return status === 'running' || status === 'queued';
}

function UnitCard({ resource, component, busy, download, onLink, onUnlink, onDownload,
  onCancel }: {
  resource: LargeResource;
  component: LargeResourceComponent;
  busy?: boolean;
  download?: LargeResourceOperation;
  onLink: (resource: LargeResource, component: LargeResourceComponent) => void;
  onUnlink: (resource: LargeResource, component: LargeResourceComponent) => void;
  onDownload: (resource: LargeResource, component: LargeResourceComponent) => void;
  onCancel: (resource: LargeResource, component: LargeResourceComponent) => void;
}) {
  const state = String(component.state || 'missing').toLowerCase();
  const linked = state === 'linked';
  const missing = missingFiles(component);
  const pendingDownload = pendingDownloads(component);
  const declared = declaredFiles(component);
  const action = unitAction(component);
  const downloading = operationActive(download);
  const status = String(download?.status || '').toLowerCase();
  // 取消或完成后按钮要回到动作文案，否则它看起来仍是“下载中”，
  // 也让用户能直接重试。
  const buttonText = download && (downloading || status === 'failed' || status === 'succeeded')
    ? downloadButtonLabel(download, action.text) : action.text;
  // 后端取消时 error 是字面量 'cancelled'，不能漏进按钮提示里。
  const buttonTitle = status === 'cancelled' ? action.reason : (download?.error || action.reason);
  // 后端没登记应校验的文件：卡片只说明它不参与就绪判定。
  const undeclared = declared.length === 0;
  return (
    <article
      className="runtime-card resource-unit-card"
      data-testid={`unit-${component.name}`}
      data-resource={resource.id}
      data-state={state}
    >
      <header className="runtime-card-head">
        <div className="runtime-card-title">
          <h3>{component.name}</h3>
          <code>{resource.title || resource.id}</code>
        </div>
        <div className="runtime-card-tags">
          <span className={`runtime-chip is-${state}`} data-state={state}>{componentStateLabel(component)}</span>
        </div>
      </header>
      <dl className="runtime-facts">
        <div><dt>{t('官方目录或文件')}</dt><dd><code>{component.name}</code></dd></div>
        <div><dt>{t('占用空间')}</dt><dd>{megabytes(component.bytes || resource.size_bytes)}</dd></div>
      </dl>
      {!linked && missing.length
        ? <details className="runtime-missing" open={missing.length <= 4}>
          <summary>{t('缺少 {n} 个文件', { n: missing.length })}</summary>
          <ul>{missing.slice(0, 12).map((name) => <li key={name}><code>{name}</code></li>)}
            {missing.length > 12 ? <li>{t('等 {n} 项', { n: missing.length - 12 })}</li> : null}
          </ul>
        </details>
        : null}
      {!linked && (component.undownloadable?.length || 0) > 0
        ? <p className="runtime-note">{t('{n} 个文件没有下载源，只能链接已有目录。',
            { n: (component.undownloadable || []).length })}</p>
        : null}
      {!linked && undeclared
        ? <>
          <p className="runtime-note">{t('该资源没有登记应校验的文件，因此不参与就绪判定')}</p>
          <details className="runtime-missing">
            <summary>{t('待补清单')}</summary>
            <p className="runtime-note">{t('已声明 {count} 项', { count: declared.length })}</p>
          </details>
        </>
        : null}
      <footer className="runtime-actions">
        {linked ? (
          <button type="button" className="subtle-button" disabled={busy}
            onClick={() => onUnlink(resource, component)}>{t('解除链接')}</button>
        ) : (
          <>
            <button type="button" className="subtle-button"
              disabled={busy || downloading || !action.enabled}
              data-action={action.enabled ? (pendingDownload.length ? 'download' : 'rsync') : 'blocked'}
              data-pending={pendingDownload.length}
              title={buttonTitle}
              onClick={() => onDownload(resource, component)}>
              {buttonText}
            </button>
            {downloading || status === 'cancelled' ? (
              <button type="button" className="subtle-button"
                disabled={busy || !downloading}
                data-action="cancel-download"
                data-download-status={downloading ? 'cancelling' : 'cancelled'}
                onClick={() => onCancel(resource, component)}>
                {downloading ? t('取消下载') : t('已取消')}
              </button>
            ) : null}
            <button type="button" className="subtle-button is-primary" disabled={busy}
              onClick={() => onLink(resource, component)}>{t('链接')}</button>
          </>
        )}
      </footer>
      {!linked && status === 'cancelled'
        ? <p className="runtime-note" data-download-status="cancelled">{t('已取消')}</p>
        : null}
    </article>
  );
}

export function LargeResourceSection({ target = '', environment, compact }: {
  target?: string;
  environment?: string;
  compact?: boolean;
}) {
  const [resources, setResources] = useState<LargeResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [link, setLink] = useState<{ resource: LargeResource; component: LargeResourceComponent } | null>(null);
  const [source, setSource] = useState('');
  const [message, setMessage] = useState('');
  const [downloads, setDownloads] = useState<Record<string, DownloadProgress>>({});
  const downloadsRef = useRef(downloads);
  const [picker, setPicker] = useState<{ open: boolean; path: string; parent: string;
    roots: string[]; entries: Array<{ name: string; path: string; directory: boolean }>;
    error: string }>({ open: false, path: '', parent: '', roots: [], entries: [], error: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const answer = await (target ? api.remoteResources(target) : api.largeResources());
      const items = Array.isArray(answer) ? answer as LargeResource[]
        : ((answer as { resources?: LargeResource[] }).resources || []);
      setResources(items);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [target]);

  useEffect(() => { void load(); }, [load]);

  const units = useMemo(() => {
    const rows: Array<{ resource: LargeResource; component: LargeResourceComponent }> = [];
    for (const resource of resourcesOf(resources, environment)) {
      for (const component of resourceComponents(resource)) {
        rows.push({ resource, component });
      }
    }
    return rows;
  }, [resources, environment]);

  const total = units.length;
  const ready = units.filter((row) => isReady(row.component)).length;

  useEffect(() => { downloadsRef.current = downloads; }, [downloads]);
  useEffect(() => { setDownloads({}); }, [target, environment]);

  const act = async (key: string, work: () => Promise<unknown>, note = '') => {
    setBusy(key);
    setMessage(note);
    try {
      await work();
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy('');
    }
  };

  const beginDownload = async (resource: LargeResource, component: LargeResourceComponent,
                               announce = true) => {
    const key = component.name;
    const count = pendingDownloads(component).length || missingFiles(component).length || 1;
    setDownloads((previous) => ({
      ...previous,
      [key]: { job: '', unit: component.name, operation: { id: '', status: 'running' } },
    }));
    if (announce) setMessage(downloadStartedMessage(component.name, count));
    const forget = () => setDownloads((previous) => {
      if (!previous[key]) return previous;
      const next = { ...previous };
      delete next[key];
      return next;
    });
    let answer: { id?: string } | undefined;
    try {
      answer = target
        ? await api.remoteResourceDownload(target, resource.id, '', false, component.name)
        : await api.largeResourceDownload(resource.id, '', false, component.name);
    } catch (err) {
      forget();
      throw err;
    }
    const job = String(answer?.id || '');
    if (!job) {
      forget();
      throw new Error(t('下载任务没有返回标识'));
    }
    setDownloads((previous) => previous[key]
      ? { ...previous, [key]: { ...previous[key], job,
        operation: { ...previous[key].operation, id: job } } }
      : previous);
    return job;
  };

  const download = (resource: LargeResource, component: LargeResourceComponent) => {
    const count = pendingDownloads(component).length || missingFiles(component).length || 1;
    void act(`download:${component.name}`, () => beginDownload(resource, component),
      downloadStartedMessage(component.name, count));
  };

  // 取消后立刻把这一项标成终态：轮询只跟踪活动任务，所以它不会再把状态翻回
  // running；按钮文案 1 秒内变成「已取消」，下载按钮同时恢复可点。
  const cancelDownload = (resource: LargeResource, component: LargeResourceComponent) => {
    const key = component.name;
    void act(`cancel:${key}`, async () => {
      if (target) await api.remoteResourceCancel(target, resource.id);
      else await api.largeResourceCancel(resource.id);
      setDownloads((previous) => previous[key] ? {
        ...previous,
        [key]: {
          ...previous[key],
          operation: { ...previous[key].operation, status: 'cancelled', error: 'cancelled' },
        },
      } : previous);
      setMessage(t('已取消'));
    });
  };

  const runningJobs = useMemo(() => Object.values(downloads)
    .filter((entry) => entry.job && operationActive(entry.operation))
    .map((entry) => entry.job).sort().join(','), [downloads]);

  useEffect(() => {
    if (!runningJobs) return;
    let alive = true;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const answer = target ? await api.remoteResources(target) : await api.largeResources();
          if (!alive || Array.isArray(answer)) return;
          const operations = new Map<string, LargeResourceOperation>();
          for (const operation of (answer as { operations?: LargeResourceOperation[] }).operations || []) {
            operations.set(String(operation.id), operation);
          }
          const terminal = Object.entries(downloadsRef.current).flatMap(([key, entry]) => {
            const operation = entry.job ? operations.get(entry.job) : undefined;
            return entry.job && operationActive(entry.operation)
              && operation && !operationActive(operation) ? [{ key, operation }] : [];
          });
          if (terminal.length) {
            if (!alive) return;
            setDownloads((previous) => {
              const next = { ...previous };
              for (const row of terminal) {
                if (next[row.key]) next[row.key] = { ...next[row.key], operation: row.operation };
              }
              return next;
            });
            await load();
            if (!alive) return;
            const statusOf = (row: { operation: LargeResourceOperation }) =>
              String(row.operation.status || '').toLowerCase();
            const failed = terminal.find((row) => statusOf(row) === 'failed');
            const cancelled = terminal.find((row) => statusOf(row) === 'cancelled');
            if (failed) setMessage(clippedError(failed.operation.error, t('下载失败')));
            else if (cancelled) setMessage(t('已取消'));
            else setMessage(t('下载完成'));
            return;
          }
          setDownloads((previous) => {
            let changed = false;
            const next = { ...previous };
            for (const [key, entry] of Object.entries(previous)) {
              if (!entry.job || !operationActive(entry.operation)) continue;
              const operation = operations.get(entry.job);
              if (!operation) continue;
              next[key] = { ...entry, operation };
              changed = true;
            }
            return changed ? next : previous;
          });
        } catch {
          // 一次快照失败不清掉进度，下一轮继续轮询。
        }
      })();
    }, 1500);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [runningJobs, target, load]);

  const unlink = (resource: LargeResource, component: LargeResourceComponent) => {
    void act(`unlink:${component.name}`, async () => {
      if (target) await api.remoteUnlinkResource(target, resource.id, component.name);
      else await api.largeResourceUnlink(resource.id, component.name);
    });
  };

  const downloadAll = () => {
    const rows = units.filter((row) => !isReady(row.component));
    if (!rows.length) return;
    void act('download-all', async () => {
      for (const row of rows) await beginDownload(row.resource, row.component, false);
    }, t('已开始下载 {n} 个单元', { n: rows.length }));
  };

  const loadPicker = async (path: string) => {
    try {
      if (target) {
        const answer = await api.browseRemote(target, path || '', 0, false) as {
          path: string; parent: string;
          entries: Array<{ name: string; path: string; directory: boolean }>;
        };
        setPicker({ open: true, path: answer.path, parent: answer.parent || '', roots: [],
          entries: (answer.entries || []).slice(0, 300), error: '' });
      } else {
        const answer = await api.browsePath(path || '', true) as unknown as {
          path: string; parent?: string; roots?: string[];
          entries: Array<{ name: string; path: string; directory: boolean }>;
        };
        setPicker({ open: true, path: answer.path, parent: answer.parent || '',
          roots: answer.roots || [], entries: (answer.entries || []).slice(0, 300), error: '' });
      }
    } catch (err) {
      setPicker((prev) => ({ ...prev, open: true,
        error: err instanceof Error ? err.message : String(err) }));
    }
  };

  const submitLink = () => {
    if (!link) return;
    const { resource, component } = link;
    void act(`link:${component.name}`, async () => {
      if (target) await api.remoteLinkResource(target, resource.id, source, true, component.name);
      else await api.largeResourceLink(resource.id, source, true, component.name);
      setLink(null);
      setSource('');
    });
  };

  return (
    <section className={`runtime-resources${compact ? ' compact' : ''}`}>
      <header className="runtime-resources-header">
        <div>
          <h3>{t('资源')}</h3>
          <p>{t('逐个下载或链接官方最小维护单元；链接不复制字节。')}</p>
        </div>
        <div className="runtime-resources-actions">
          <span>{ready}/{total}</span>
          <button type="button" className="subtle-button" onClick={() => void load()} disabled={loading}>{t('刷新')}</button>
          <button type="button" className="primary-button" onClick={downloadAll}
            disabled={loading || !total || busy === 'download-all'}>
            {t('全部安装')}
          </button>
        </div>
      </header>
      {error ? <p className="runtime-error">{error}</p> : null}
      {message ? <p className="runtime-error">{message}</p> : null}
      {loading ? <p>{t('正在读取大型资源…')}</p> : null}
      {total ? <div className="resource-unit-grid">
        {units.map(({ resource, component }) => (
          <UnitCard
            key={`${resource.id}:${component.name}`}
            resource={resource}
            component={component}
            download={downloads[component.name]?.operation}
            busy={busy === `download:${component.name}` || busy === `unlink:${component.name}`
              || busy === `cancel:${component.name}` || busy === 'download-all'}
            onLink={(item, part) => { setLink({ resource: item, component: part }); setSource(''); }}
            onUnlink={unlink}
            onDownload={download}
            onCancel={cancelDownload}
          />
        ))}
      </div> : null}
      {link ? (
        <Modal title={`${t('链接')} · ${link.component.name}`} onClose={() => setLink(null)}>
          <div className="link-form">
            <p className="link-form-lead">
              {t('把这个维护单元指向本机已有的官方目录或文件，不复制字节。')}
            </p>
            <label className="link-form-field">
              <span className="link-form-label">
                {t('源路径')}
                <code>{link.component.name}</code>
              </span>
              <div className="link-form-row">
                <input value={source} onChange={(event) => setSource(event.target.value)}
                  placeholder={t('输入该目录或文件的绝对路径')} spellCheck={false} autoFocus />
                <button type="button" className="subtle-button"
                  onClick={() => void loadPicker(source.trim())}>{t('浏览…')}</button>
              </div>
            </label>
            <ul className="link-form-hint">
              <li>{t('目录名或文件名应与官方一致：{name}。', { name: link.component.name })}</li>
              <li>{t('链接只在执行它的那台机器上生效，不会把远端文件映射到本机。')}</li>
            </ul>
          </div>
          <div className="link-form-actions">
            <button type="button" className="subtle-button" onClick={() => setLink(null)}>{t('取消')}</button>
            <button type="button" className="primary-button" disabled={!source.trim()} onClick={submitLink}>
              {t('链接')}
            </button>
          </div>
        </Modal>
      ) : null}
      {picker.open ? (
        <Modal title={t('选择目录或文件')} onClose={() => setPicker((prev) => ({ ...prev, open: false }))}>
          <div className="picker">
            <div className="picker-bar">
              <button type="button" className="subtle-button" disabled={!picker.path}
                onClick={() => void loadPicker(picker.parent)}>{t('上级')}</button>
              <code className="picker-path">{picker.path || t('根目录')}</code>
            </div>
            {picker.roots.length > 1 ? (
              <div className="picker-roots">
                {picker.roots.map((drive) => (
                  <button type="button" key={drive} className="subtle-button"
                    onClick={() => void loadPicker(drive)}>{drive}</button>
                ))}
              </div>
            ) : null}
            {picker.error ? <p className="runtime-error">{picker.error}</p> : null}
            <ul className="picker-list">
              {picker.entries.map((entry) => (
                <li key={entry.path}>
                  <button type="button" className="picker-entry"
                    onClick={() => {
                      if (entry.directory) {
                        void loadPicker(entry.path);
                      } else {
                        setSource(entry.path);
                        setPicker((prev) => ({ ...prev, open: false }));
                      }
                    }}>
                    <span aria-hidden>{entry.directory ? '📁' : '📄'}</span>
                    <span>{entry.name}</span>
                  </button>
                </li>
              ))}
              {!picker.entries.length && !picker.error ? <li className="picker-empty">{t('该目录下没有可选择的项。')}</li> : null}
            </ul>
          </div>
          <div className="link-form-actions">
            <button type="button" className="subtle-button"
              onClick={() => setPicker((prev) => ({ ...prev, open: false }))}>{t('取消')}</button>
            <button type="button" className="primary-button" disabled={!picker.path}
              onClick={() => {
                setSource(picker.path);
                setPicker((prev) => ({ ...prev, open: false }));
              }}>{t('选择此文件夹')}</button>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}
