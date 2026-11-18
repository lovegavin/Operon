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
      return t('未检查');
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

export function isReady(component: LargeResourceComponent): boolean {
  const state = String(component.state || '').toLowerCase();
  return state === 'present' || state === 'linked';
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
  return (
    <article
      className="environment-card resource-unit-card"
      data-testid={`unit-${component.name}`}
      data-resource={resource.id}
      data-state={state}
    >
      <header>
        <strong>{component.name}</strong>
        <span className="resource-chip" data-state={state}>{componentStateLabel(component)}</span>
      </header>
      <div className="environment-facts">
        <span>{t('所属资源')}</span><span>{resource.title || resource.id}</span>
        <span>{t('占用空间')}</span><span>{megabytes(component.bytes || resource.size_bytes)}</span>
      </div>
      <div className="resource-row-actions">
        {linked ? (
          <button type="button" disabled={busy} onClick={() => onUnlink(resource, component)}>{t('解除链接')}</button>
        ) : (
          <>
            <button type="button" disabled={busy} onClick={() => onDownload(resource, component)}>{t('下载')}</button>
            <button type="button" disabled={busy} onClick={() => onLink(resource, component)}>{t('链接')}</button>
          </>
        )}
      </div>
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
      if (target) await api.remoteResourceDownload(target, resource.id, '', false);
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
        if (target) await api.remoteResourceDownload(target, row.resource.id, '', false);
        else await api.largeResourceDownload(row.resource.id, '', false, row.component.name);
      }
    });
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
          <button type="button" onClick={() => void load()} disabled={loading}>{t('刷新')}</button>
          <button type="button" onClick={downloadAll} disabled={loading || !total || busy === 'download-all'}>
            {t('全部下载')}
          </button>
        </div>
      </header>
      {error ? <p className="runtime-error">{error}</p> : null}
      {message ? <p className="runtime-error">{message}</p> : null}
      {loading ? <p>{t('正在读取大型资源…')}</p> : null}
      {!loading && !total ? <p>{t('当前环境没有登记资源。')}</p> : null}
      <div className="resource-unit-grid">
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
      </div>
      {link ? (
        <Modal title={`${link.component.name} · ${t('链接目录')}`} onClose={() => setLink(null)}>
          <p>{t('请选择官方维护单元 {unit} 在本机已有的绝对路径。', { unit: link.component.name })}</p>
          <label>
            <span>{t('绝对路径')}</span>
            <input value={source} onChange={(event) => setSource(event.target.value)} placeholder={t('输入已有目录的绝对路径')} />
          </label>
          <p className="runtime-hint">{t('链接只作用于执行它的那台机器的本地文件系统，不会把远端文件映射到本机，也不复制字节。')}</p>
          <div className="modal-actions">
            <button type="button" onClick={() => setLink(null)}>{t('取消')}</button>
            <button type="button" disabled={!source.trim()} onClick={submitLink}>{t('链接')}</button>
          </div>
        </Modal>
      ) : null}
    </section>
  );
}
