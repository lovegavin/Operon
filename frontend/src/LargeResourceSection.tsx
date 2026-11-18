import {useEffect, useMemo, useState} from 'react';
import {Modal} from './RouteDialogs';
import {t} from './i18n';
import {api} from './api';
import type {LargeResource, LargeResourceComponent, LargeResourceSnapshot} from './types';

export type ResourceTarget = {id: string; name: string};

export type ResourceState = 'linked' | 'downloaded' | 'partial' | 'missing';

/** Filesystem truth wins: a link created by hand still reports linked. */
export function resourceState(resource: LargeResource): ResourceState {
  const value = String(resource.state || '');
  if (value === 'linked' || value === 'downloaded' || value === 'partial' || value === 'missing')
    return value;
  if (resource.linked) return 'linked';
  if (resource.status === 'ok') return 'downloaded';
  if (resource.status === 'partial') return 'partial';
  return 'missing';
}

export function resourceStateLabel(resource: LargeResource): string {
  switch (resourceState(resource)) {
    case 'linked':
      return t('已链接');
    case 'downloaded':
      return t('已下载');
    case 'partial':
      return t('部分就位');
    default:
      return t('缺失');
  }
}

/** The name the vendor uses for the directory or file users must link. */
export function officialRoot(resource: LargeResource): string {
  return String(resource.official_root || resource.id);
}

export function missingFiles(resource: LargeResource): string[] {
  const declared = resource.missing;
  if (Array.isArray(declared) && declared.length) return declared.map(String);
  const expected = resource.expected_files || [];
  if (resourceState(resource) === 'missing') return expected.map(String);
  return [];
}

/** Official maintenance units keep their own state; a missing unit is still listed. */
export function resourceComponents(resource: LargeResource): LargeResourceComponent[] {
  if (resource.components?.length) return resource.components;
  const name = officialRoot(resource);
  return [{name, state: resourceState(resource) === 'missing' ? 'missing' : 'present'}];
}

export function componentStateLabel(component: LargeResourceComponent): string {
  switch (String(component.state || '')) {
    case 'present':
      return t('已就位');
    case 'partial':
      return t('部分就位');
    case 'unknown':
      return t('未检查');
    default:
      return t('缺失');
  }
}

/** Group by the environment whose operators consume the resource. */
export function groupResources(resources: LargeResource[]): Array<{environment: string; items: LargeResource[]}> {
  const groups = new Map<string, LargeResource[]>();
  for (const resource of resources) {
    const names = resource.environments?.length ? resource.environments : [''];
    for (const name of names) {
      const key = String(name || '');
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(resource);
    }
  }
  return [...groups.entries()]
    .sort(([left], [right]) => (left === '' ? 1 : right === '' ? -1 : left.localeCompare(right)))
    .map(([environment, items]) => ({
      environment,
      items: items.sort((a, b) => String(a.title || a.id).localeCompare(String(b.title || b.id))),
    }));
}

/** Resources consumed by one environment. */
export function resourcesOf(resources: LargeResource[], environment: string): LargeResource[] {
  if (!environment) return resources;
  return resources.filter((resource) => (resource.environments || []).includes(environment));
}

export function UnitRow({unit, busy, onLink, onUnlink}: {
  unit: LargeResourceComponent;
  busy: boolean;
  onLink: (unit: LargeResourceComponent) => void;
  onUnlink: (unit: LargeResourceComponent) => void;
}) {
  const state = String(unit.state || 'missing');
  const linked = state === 'present' && !!unit.linked;
  return (
    <li className="resource-unit" data-testid={`unit-${unit.name}`} data-state={state}>
      <div className="resource-unit-name">
        <code>{unit.name}</code>
        {unit.note ? <span className="resource-unit-note">{unit.note}</span> : null}
      </div>
      <span className={`resource-chip is-${state === 'present' ? 'linked' : state}`}>{componentStateLabel(unit)}</span>
      <span className="resource-unit-size">{bytes(unit.bytes || (unit.size_mb || 0) * 1024 * 1024)}</span>
      <span className="resource-unit-actions">
        <button type="button" className="ghost" disabled={busy} onClick={() => onLink(unit)}>{t('链接')}</button>
        {linked ? <button type="button" className="ghost" disabled={busy} onClick={() => onUnlink(unit)}>{t('解除')}</button> : null}
      </span>
    </li>
  );
}

export function ResourceCard({resource, busy, onLink, onUnlink, onDownload}: {
  resource: LargeResource;
  busy: boolean;
  onLink: (unit: LargeResourceComponent) => void;
  onUnlink: (unit: LargeResourceComponent) => void;
  onDownload: () => void;
}) {
  const state = resourceState(resource);
  const units = resourceComponents(resource);
  return (
    <article className="environment-card resource-card" data-state={state} data-testid={`resource-${resource.id}`}>
      <header className="environment-card-head">
        <div>
          <h3>{resource.title || resource.id}</h3>
          <p className="resource-id">{t('官方目录或文件：{name}', {name: officialRoot(resource)})}</p>
        </div>
        <span className={`resource-chip is-${state}`}>{resourceStateLabel(resource)}</span>
      </header>
      <ul className="resource-units">
        {units.map((unit) => (
          <UnitRow key={unit.name} unit={unit} busy={busy} onLink={onLink} onUnlink={onUnlink}/>
        ))}
      </ul>
      <footer className="resource-row-actions">
        <span className="resource-unit-size">{bytes(resource.size_bytes)}</span>
        <button type="button" className="ghost" disabled={busy} onClick={onDownload}>{t('下载全部')}</button>
      </footer>
    </article>
  );
}

export function LargeResourceSection({target, targets = [], onTarget = () => {}, environment = '',
                                     compact = false, resources: supplied}: {
  target: string;
  targets?: ResourceTarget[];
  onTarget?: (value: string) => void;
  environment?: string;
  compact?: boolean;
  resources?: LargeResource[];
}) {
  const [snapshot, setSnapshot] = useState<LargeResourceSnapshot | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [draft, setDraft] = useState<{resource: LargeResource; unit: LargeResourceComponent; source: string} | null>(null);

  const load = async () => {
    if (supplied) return;
    try {
      setSnapshot(target ? await api.remoteResources(target) : await api.largeResources());
      setError('');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, supplied]);

  const resources = useMemo(() => resourcesOf(supplied || snapshot?.resources || [], environment),
    [supplied, snapshot, environment]);
  const groups = useMemo(() => groupResources(resources), [resources]);

  const submit = async () => {
    if (!draft) return;
    const source = draft.source.trim();
    if (!source) {
      setError(t('请填写本机上已有的绝对路径。'));
      return;
    }
    setBusy(draft.resource.id);
    try {
      const result = target
        ? await api.remoteLinkResource(target, draft.resource.id, source, true, draft.unit.name)
        : await api.largeResourceLink(draft.resource.id, source, true, draft.unit.name);
      setMessage(t('已链接：{target}', {target: result.root || source}));
      setDraft(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const unlink = async (resource: LargeResource, unit: LargeResourceComponent) => {
    setBusy(resource.id);
    try {
      if (target) await api.remoteUnlinkResource(target, resource.id, unit.name);
      else await api.largeResourceUnlink(resource.id, unit.name);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const download = async (resource: LargeResource) => {
    setBusy(resource.id);
    try {
      await api.largeResourceDownload(resource.id);
      setMessage(t('已开始下载'));
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const body = (
    <>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-notice">{message}</p> : null}
      {!supplied && !snapshot ? <p className="settings-note">{t('正在读取大型资源…')}</p> : null}
      {resources.length === 0 && snapshot ? <p className="settings-note">{t('当前环境没有登记资源。')}</p> : null}
      {compact ? (
        <div className="runtime-grid">
          {resources.map((resource) => (
            <ResourceCard key={resource.id} resource={resource} busy={busy === resource.id}
              onLink={(unit) => { setDraft({resource, unit, source: resource.link_roots?.[0] || ''}); setError(''); }}
              onUnlink={(unit) => void unlink(resource, unit)}
              onDownload={() => void download(resource)}/>
          ))}
        </div>
      ) : groups.map((group) => (
        <div className="resource-group" key={group.environment || 'other'}>
          <div className="resource-group-head">
            <h4>{group.environment ? t('环境：{name}', {name: group.environment}) : t('其他资源')}</h4>
            <span className="resource-group-count">{group.items.length}</span>
          </div>
          <div className="runtime-grid">
            {group.items.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} busy={busy === resource.id}
                onLink={(unit) => { setDraft({resource, unit, source: resource.link_roots?.[0] || ''}); setError(''); }}
                onUnlink={(unit) => void unlink(resource, unit)}
                onDownload={() => void download(resource)}/>
            ))}
          </div>
        </div>
      ))}
      {draft ? (
        <Modal title={`${draft.resource.title || draft.resource.id} · ${t('链接 {unit}', {unit: draft.unit.name})}`}
          onClose={() => setDraft(null)}>
          <p className="settings-note">
            {t('请选择官方维护单元 {unit} 在本机已有的绝对路径。', {unit: draft.unit.name})}
          </p>
          <label className="field">
            <span>{t('绝对路径')}</span>
            <input value={draft.source}
              placeholder={draft.resource.link_roots?.[0] || t('请填写本机上已有的绝对路径。')}
              onChange={(event) => setDraft({...draft, source: event.target.value})}/>
          </label>
          <p className="settings-note">{t('链接只作用于执行它的那台机器的本地文件系统，不会把远端文件映射到本机，也不复制字节。')}</p>
          <footer className="dialog-actions">
            <button type="button" className="ghost" onClick={() => setDraft(null)}>{t('取消')}</button>
            <button type="button" disabled={!!busy} onClick={() => void submit()}>{t('链接')}</button>
          </footer>
        </Modal>
      ) : null}
    </>
  );

  if (compact) return <div className="runtime-resources is-compact">{body}</div>;

  return (
    <section className="runtime-resources">
      <header className="runtime-resources-head">
        <div>
          <h3>{t('大型资源与模型权重')}</h3>
          <p className="settings-note">{t('按执行位置与环境查看缺失的数据库或权重；链接只在本机建一个指向，不复制字节。')}</p>
        </div>
        <div className="runtime-resources-actions">
          <label className="field inline">
            <span>{t('执行位置')}</span>
            <select className="select-compact" value={target}
              aria-label={`${t('执行位置')}: ${target || t('本地')}`}
              onChange={(event) => onTarget(event.target.value)}>
              <option value="">{t('本地')}</option>
              {targets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <button type="button" className="ghost" onClick={() => void load()}>{t('刷新')}</button>
        </div>
      </header>
      {body}
    </section>
  );
}

function bytes(value?: number): string {
  const total = Number(value || 0);
  if (!total) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let index = 0;
  let size = total;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
