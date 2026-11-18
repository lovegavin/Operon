import {useCallback, useEffect, useState} from 'react';
import {Modal} from './RouteDialogs';
import {t} from './i18n';
import {api} from './api';
import type {LargeResource, LargeResourceSnapshot, LargeResourceUnit} from './types';

export type ResourceTarget = {id: string; name: string};

export type ResourceDraft = {name: string; unit: string; title: string; source: string};

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

export function unitState(unit: LargeResourceUnit): ResourceState {
  const value = String(unit.state || '');
  if (value === 'linked' || value === 'downloaded' || value === 'partial' || value === 'missing')
    return value;
  return unit.receipt ? 'downloaded' : 'missing';
}

export function unitStateLabel(unit: LargeResourceUnit): string {
  switch (unitState(unit)) {
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

/** Group by the environment whose operators consume the resource. */
export function groupResources(resources: LargeResource[]): Array<{environment: string; items: LargeResource[]}> {
  const groups = new Map<string, LargeResource[]>();
  for (const resource of resources) {
    const keys = resource.environments && resource.environments.length ? resource.environments : [''];
    for (const key of keys) {
      const bucket = groups.get(key) || [];
      if (!bucket.includes(resource)) bucket.push(resource);
      groups.set(key, bucket);
    }
  }
  return [...groups.entries()]
    .map(([environment, items]) => ({environment, items}))
    .sort((left, right) => {
      if (!left.environment) return right.environment ? 1 : 0;
      if (!right.environment) return -1;
      return left.environment.localeCompare(right.environment);
    });
}

function humanBytes(value?: number): string {
  if (!value) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 || index === 0 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}

export function ResourceRow({resource, busy, onLink, onUnlink}: {
  resource: LargeResource;
  busy: boolean;
  onLink: (draft: ResourceDraft) => void;
  onUnlink: (name: string, unit: string) => void;
}) {
  const state = resourceState(resource);
  const units = resource.units || [];
  const perUnit = resource.link_unit === 'items' && units.length > 0;
  const target = resource.link_target || resource.source || '';
  return <article className="resource-row" data-testid={`resource-${resource.id}`} data-state={state}>
    <header className="resource-row-head">
      <div className="resource-row-title">
        <h4>{resource.title || resource.id}</h4>
        <code>{resource.id}</code>
      </div>
      <span className={`resource-chip is-${state}`}>{resourceStateLabel(resource)}</span>
    </header>
    {target && <p className="resource-target" title={target}>{t('链接来源：')} <code>{target}</code></p>}
    <dl className="resource-facts">
      <div><dt>{t('占用空间')}</dt><dd>{humanBytes(resource.size_bytes)}</dd></div>
      <div><dt>{t('链接单元')}</dt><dd>{perUnit ? t('逐项') : t('整树')}</dd></div>
      <div><dt>{t('消费算子')}</dt><dd>{(resource.used_by || []).length || t('无')}</dd></div>
    </dl>
    {perUnit
      ? <ul className="resource-units">{units.map(unit => {
        const value = unitState(unit);
        return <li key={unit.name} className="resource-unit" data-state={value}>
          <code title={unit.target || unit.name}>{unit.name}</code>
          <span className={`resource-chip is-${value}`}>{unitStateLabel(unit)}</span>
          <span className="resource-unit-actions">
            {value === 'linked'
              ? <button className="subtle-button" disabled={busy}
                  onClick={() => onUnlink(resource.id, unit.name)}>{t('解除')}</button>
              : <button className="subtle-button is-primary" disabled={busy}
                  onClick={() => onLink({name: resource.id, unit: unit.name,
                    title: unit.title || unit.name, source: ''})}>{t('链接')}</button>}
          </span>
        </li>;
      })}</ul>
      : <footer className="resource-row-actions">
        <button className="subtle-button is-primary" disabled={busy}
          onClick={() => onLink({name: resource.id, unit: 'tree', title: resource.title || resource.id, source: ''})}>
          {t('链接已有目录')}</button>
        {state === 'linked' && <button className="subtle-button" disabled={busy}
          onClick={() => onUnlink(resource.id, 'tree')}>{t('解除链接')}</button>}
      </footer>}
  </article>;
}

export function LargeResourceSection({target, targets, onTarget}: {
  target: string;
  targets: ResourceTarget[];
  onTarget: (value: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<LargeResourceSnapshot | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [draft, setDraft] = useState<ResourceDraft | null>(null);

  const load = useCallback(async () => {
    try {
      const value = target ? await api.remoteResources(target) : await api.largeResources();
      setSnapshot(value);
      setError('');
    } catch (failure) {
      setError((failure as Error).message);
    }
  }, [target]);

  useEffect(() => { void load(); }, [load]);

  async function submit() {
    if (!draft) return;
    const source = draft.source.trim();
    if (!source) {
      setError(t('请填写本机上已有的绝对路径。'));
      return;
    }
    setBusy(draft.name);
    setMessage('');
    setError('');
    try {
      if (target) await api.remoteLinkResource(target, draft.name, source, true, draft.unit);
      else await api.largeResourceLink(draft.name, source, true, draft.unit);
      setMessage(t('已链接：{target}', {target: source}));
      setDraft(null);
      await load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function unlink(name: string, unit: string) {
    setBusy(name);
    setError('');
    setMessage('');
    try {
      if (target) await api.remoteUnlinkResource(target, name, unit);
      else await api.largeResourceUnlink(name, unit);
      setMessage(t('已解除链接'));
      await load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy('');
    }
  }

  const resources = snapshot?.resources || [];
  const groups = groupResources(resources);
  const current = draft ? resources.find(resource => resource.id === draft.name) : undefined;
  const suggested = current?.link_roots?.[0] || '';

  return <section className="runtime-resources" aria-label={t('大型资源与模型权重')}>
    <header className="runtime-resources-head">
      <div>
        <h3>{t('大型资源与模型权重')}</h3>
        <p className="muted">{t('按执行位置与环境查看缺失的数据库或权重；链接只在本机建一个指向，不复制字节。')}</p>
      </div>
      <div className="runtime-resources-actions">
        <label className="runtime-target">
          <span>{t('执行位置')}</span>
          <select value={target} disabled={Boolean(busy)} onChange={event => onTarget(event.target.value)}>
            <option value="">{t('本地')}</option>
            {targets.map(remote => <option key={remote.id} value={remote.id}>{remote.name}</option>)}
          </select>
        </label>
        <button className="subtle-button" disabled={Boolean(busy)} onClick={() => void load()}>{t('刷新')}</button>
      </div>
    </header>
    {error && <pre className="modal-error">{error}</pre>}
    {message && <p className="settings-note">{message}</p>}
    {!snapshot && !error && <p className="muted">{t('正在读取大型资源…')}</p>}
    {snapshot && !resources.length && <p className="muted">{t('当前库没有声明大型资源。')}</p>}
    {groups.map(group => <div className="resource-group" key={group.environment || 'other'}>
      <h4 className="resource-group-head">
        {group.environment ? t('环境：{name}', {name: group.environment}) : t('其他资源')}
        <span className="resource-group-count">{group.items.length}</span>
      </h4>
      {group.items.map(resource => <ResourceRow key={resource.id} resource={resource}
        busy={busy === resource.id} onLink={value => { setDraft(value); setError(''); }} onUnlink={unlink}/>)}
    </div>)}
    {draft && <Modal title={t('链接{name}', {name: draft.title})} onClose={() => setDraft(null)}>
      <div className="resource-dialog">
        <p className="settings-note">{t('填这份内容在本机上的绝对路径；链接建好后 Operon 从资源根目录读取，字节不复制。')}</p>
        {suggested && <p className="muted">{t('建议位置：{path}', {path: suggested})}</p>}
        <label className="field">
          <span>{t('绝对路径')}</span>
          <input autoFocus value={draft.source} disabled={Boolean(busy)}
            placeholder={suggested || t('/绝对/路径')}
            onChange={event => setDraft({...draft, source: event.target.value})}/>
        </label>
        <p className="muted">{t('链接单元：{unit}（按官方维护的最小单元）', {unit: draft.unit === 'tree' ? t('整树') : draft.unit})}</p>
        <div className="runtime-actions">
          <button className="primary-button" disabled={Boolean(busy)} onClick={() => void submit()}>{t('链接')}</button>
          <button className="subtle-button" disabled={Boolean(busy)} onClick={() => setDraft(null)}>{t('取消')}</button>
        </div>
      </div>
    </Modal>}
  </section>;
}
