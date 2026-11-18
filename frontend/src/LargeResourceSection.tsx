import {useEffect, useMemo, useState} from 'react';
import {Modal} from './RouteDialogs';
import {t} from './i18n';
import {api} from './api';
import type {LargeResource, LargeResourceSnapshot} from './types';

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

export function ResourceCard({resource, onOpen, onLink}: {
  resource: LargeResource;
  onOpen: (resource: LargeResource) => void;
  onLink: (resource: LargeResource) => void;
}) {
  const state = resourceState(resource);
  const missing = missingFiles(resource).length;
  return (
    <article className="environment-card resource-card" data-state={state} data-testid={`resource-${resource.id}`}>
      <header className="environment-card-head">
        <div>
          <h3>{resource.title}</h3>
          <p className="resource-id">{resource.id}</p>
        </div>
        <span className={`resource-chip is-${state}`}>{resourceStateLabel(resource)}</span>
      </header>
      <dl className="environment-facts">
        <dt>{t('官方目录或文件')}</dt>
        <dd><code>{officialRoot(resource)}</code></dd>
        <dt>{t('占用空间')}</dt>
        <dd>{bytes(resource.size_bytes)}</dd>
        <dt>{t('消费算子')}</dt>
        <dd>{resource.used_by?.length || 0}</dd>
        <dt>{t('链接单元')}</dt>
        <dd>{t('整棵目录')}</dd>
      </dl>
      {state === 'partial' ? <p className="resource-warning">{t('缺少 {count} 个文件', {count: missing})}</p> : null}
      <footer className="resource-row-actions">
        <button type="button" className="ghost" onClick={() => onOpen(resource)}>{t('查看缺失项')}</button>
        <button type="button" onClick={() => onLink(resource)}>{t('链接目录')}</button>
      </footer>
    </article>
  );
}

export function LargeResourceSection({target, targets, onTarget}: {
  target: string;
  targets: ResourceTarget[];
  onTarget: (value: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<LargeResourceSnapshot | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [detail, setDetail] = useState<LargeResource | null>(null);
  const [draft, setDraft] = useState<{resource: LargeResource; source: string} | null>(null);

  const load = async () => {
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
  }, [target]);

  const resources = snapshot?.resources || [];
  const groups = useMemo(() => groupResources(resources), [resources]);

  const submit = async () => {
    if (!draft) return;
    const name = draft.resource.id;
    const source = draft.source.trim();
    if (!source) {
      setError(t('请填写本机上已有的绝对路径。'));
      return;
    }
    setBusy(name);
    try {
      const result = target
        ? await api.remoteLinkResource(target, name, source, true)
        : await api.largeResourceLink(name, source, true);
      setMessage(t('已链接：{target}', {target: result.root || source}));
      setDraft(null);
      setDetail(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy('');
    }
  };

  const unlink = async (resource: LargeResource) => {
    setBusy(resource.id);
    try {
      if (target) await api.remoteUnlinkResource(target, resource.id);
      else await api.largeResourceUnlink(resource.id);
      setDetail(null);
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

  const current = detail ? resources.find((item) => item.id === detail.id) || detail : null;

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
            <select
              className="select-compact"
              value={target}
              aria-label={`${t('执行位置')}: ${target || t('本地')}`}
              onChange={(event) => onTarget(event.target.value)}
            >
              <option value="">{t('本地')}</option>
              {targets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <button type="button" className="ghost" onClick={() => void load()}>{t('刷新')}</button>
        </div>
      </header>
      {error ? <p className="form-error">{error}</p> : null}
      {message ? <p className="form-notice">{message}</p> : null}
      {!snapshot ? <p className="settings-note">{t('正在读取大型资源…')}</p> : null}
      {snapshot && resources.length === 0 ? <p className="settings-note">{t('当前库没有声明大型资源。')}</p> : null}
      {groups.map((group) => (
        <div className="resource-group" key={group.environment || 'other'}>
          <div className="resource-group-head">
            <h4>{group.environment ? t('环境：{name}', {name: group.environment}) : t('其他资源')}</h4>
            <span className="resource-group-count">{group.items.length}</span>
          </div>
          <div className="runtime-grid">
            {group.items.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} onOpen={setDetail} onLink={(item) => {
                setDraft({resource: item, source: item.link_roots?.[0] || ''});
                setError('');
              }}/>
            ))}
          </div>
        </div>
      ))}
      {current ? (
        <Modal title={`${current.title} · ${t('所需文件')}`} onClose={() => setDetail(null)}>
          <p className="settings-note">
            {t('官方目录或文件：{name}。链接后 Operon 会检查其中缺失的文件。', {name: officialRoot(current)})}
          </p>
          <ul className="resource-units">
            {(current.expected_files || []).map((name) => {
              const missing = missingFiles(current).includes(name);
              return (
                <li key={name} className="resource-unit">
                  <code>{name}</code>
                  <span className={`resource-chip is-${missing ? 'missing' : 'linked'}`}>
                    {missing ? t('缺失') : t('已就位')}
                  </span>
                </li>
              );
            })}
          </ul>
          <footer className="dialog-actions">
            <button type="button" className="ghost" onClick={() => {
              setDraft({resource: current, source: current.link_roots?.[0] || ''});
            }}>{t('重新链接该目录')}</button>
            <button type="button" className="ghost" disabled={busy === current.id}
              onClick={() => void download(current)}>{t('下载')}</button>
            <button type="button" className="ghost" disabled={busy === current.id}
              onClick={() => void unlink(current)}>{t('解除链接')}</button>
            <button type="button" onClick={() => setDetail(null)}>{t('关闭')}</button>
          </footer>
        </Modal>
      ) : null}
      {draft ? (
        <Modal title={`${draft.resource.title} · ${t('链接目录')}`} onClose={() => setDraft(null)}>
          <p className="settings-note">
            {t('请选择官方目录或文件：{name}。', {name: officialRoot(draft.resource)})}
          </p>
          <label className="field">
            <span>{t('绝对路径')}</span>
            <input
              value={draft.source}
              placeholder={draft.resource.link_roots?.[0] || t('请填写本机上已有的绝对路径。')}
              onChange={(event) => setDraft({...draft, source: event.target.value})}
            />
          </label>
          <p className="settings-note">{t('链接只作用于执行它的那台机器的本地文件系统，不会把远端文件映射到本机，也不复制字节。')}</p>
          <footer className="dialog-actions">
            <button type="button" className="ghost" onClick={() => setDraft(null)}>{t('取消')}</button>
            <button type="button" disabled={!!busy} onClick={() => void submit()}>{t('链接')}</button>
          </footer>
        </Modal>
      ) : null}
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
