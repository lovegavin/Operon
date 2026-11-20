import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { Modal } from './RouteDialogs';
import { t } from './i18n';
import type { LargeResource, LargeResourceComponent } from './types';

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
    text: t('缺 {count} 个文件，没有 HTTP/rsync 源', { count: missing.length }),
    enabled: false,
    reason: t('{n} 个文件没有 HTTP 下载源，只能链接已有目录。', { n: missing.length }),
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

function UnitCard({ resource, component, busy, onLink, onUnlink, onDownload }: {
  resource: LargeResource;
  component: LargeResourceComponent;
  busy?: boolean;
  onLink: (resource: LargeResource, component: LargeResourceComponent) => void;
  onUnlink: (resource: LargeResource, component: LargeResourceComponent) => void;
  onDownload: (resource: LargeResource, component: LargeResourceComponent) => void;
}) {
  const state = String(component.state || 'missing').toLowerCase();
  const linked = state === 'linked';
  const missing = missingFiles(component);
  const pendingDownload = pendingDownloads(component);
  const declared = declaredFiles(component);
  const action = unitAction(component);
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
        ? <p className="runtime-note">{t('{n} 个文件没有 HTTP 下载源，只能链接已有目录。',
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
              disabled={busy || !action.enabled}
              data-action={action.enabled ? (pendingDownload.length ? 'download' : 'rsync') : 'blocked'}
              data-pending={pendingDownload.length}
              title={action.reason}
              onClick={() => onDownload(resource, component)}>
              {action.text}
            </button>
            <button type="button" className="subtle-button is-primary" disabled={busy}
              onClick={() => onLink(resource, component)}>{t('链接')}</button>
          </>
        )}
      </footer>
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

  const act = async (key: string, work: () => Promise<unknown>) => {
    setBusy(key);
    setMessage('');
    try {
      await work();
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy('');
    }
  };

  const download = (resource: LargeResource, component: LargeResourceComponent) => {
    void act(`download:${component.name}`, async () => {
      if (target) await api.remoteResourceDownload(target, resource.id, '', false, component.name);
      else await api.largeResourceDownload(resource.id, '', false, component.name);
    });
  };

  const unlink = (resource: LargeResource, component: LargeResourceComponent) => {
    void act(`unlink:${component.name}`, async () => {
      if (target) await api.remoteUnlinkResource(target, resource.id, component.name);
      else await api.largeResourceUnlink(resource.id, component.name);
    });
  };

  const downloadAll = () => {
    void act('download-all', async () => {
      for (const row of units) {
        if (isReady(row.component)) continue;
        if (target) await api.remoteResourceDownload(target, row.resource.id, '', false, row.component.name);
        else await api.largeResourceDownload(row.resource.id, '', false, row.component.name);
      }
    });
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
            busy={busy === `download:${component.name}` || busy === `unlink:${component.name}` || busy === 'download-all'}
            onLink={(item, part) => { setLink({ resource: item, component: part }); setSource(''); }}
            onUnlink={unlink}
            onDownload={download}
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
