import {t} from './i18n';
import {useEffect, useState} from 'react';
import {ArrowsClockwise, Link, LinkBreak} from '@phosphor-icons/react';
import {api, ApiError} from './api';
import type {LargeResource, LargeResourceSnapshot} from './types';
import './largeResources.css';

function bytes(value: number | undefined) {
  if (!value) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = value, index = 0;
  while (size >= 1024 && index < units.length - 1) {size /= 1024; index += 1;}
  return `${index === 0 || size >= 10 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}

function stateLabel(resource: LargeResource) {
  if (resource.linked) return t("已外链");
  if (resource.present) return t("已就位");
  return resource.status === 'partial' ? t("不完整") : t("缺失");
}

export type LinkEnvironment = {name: string; status: string; title?: string};
type Target = {id: string; name: string};
type Draft = {name: string; source: string; target: string; environment: string};

export function missingEnvironments(options: LinkEnvironment[]): LinkEnvironment[] {
  return options.filter(option => option.status !== 'ready');
}

export function linkCandidates(resources: LargeResource[], environment: string, keep = ''): LargeResource[] {
  return resources.filter(resource => {
    if (!(resource.link_roots || []).length) return false;
    if (environment && !(resource.environments || []).includes(environment)) return false;
    return !resource.present || resource.id === keep;
  });
}

export function LargeResources() {
  const [snapshot, setSnapshot] = useState<LargeResourceSnapshot | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [environments, setEnvironments] = useState<LinkEnvironment[]>([]);
  useEffect(() => {
    let alive = true;
    api.largeResources().then(value => {if (alive) setSnapshot(value);})
      .catch(e => {if (alive) setError(e instanceof Error ? e.message : String(e));});
    api.pool().then(value => {
      if (alive) setTargets((value.remotes || []).filter(remote => remote.connected)
        .map(remote => ({id: remote.profile.id, name: remote.profile.name})));
    }).catch(() => {});
    return () => {alive = false;};
  }, []);
  const openTarget = draft ? draft.target : null;
  useEffect(() => {
    if (openTarget === null) return;
    let alive = true;
    const load = openTarget
      ? api.remoteEnvironments(openTarget).then(value => Object.entries(value.environments || {}).map(([name, entry]) =>
        ({name, status: String(entry.status || ''), title: entry.name})))
      : api.environments().then(value => Object.entries(value.environments || {}).map(([name, entry]) =>
        ({name, status: entry.status, title: entry.title})));
    load.then(list => {if (alive) setEnvironments(list);}).catch(() => {if (alive) setEnvironments([]);});
    return () => {alive = false;};
  }, [openTarget]);
  async function run(action: () => Promise<void>, success: string) {
    setBusy(true); setError(''); setMessage('');
    try {await action(); setMessage(success);}
    catch (e) {setError(e instanceof Error ? e.message : String(e));}
    finally {setBusy(false);}
  }
  async function reload() {setSnapshot(await api.largeResources());}
  const resources = snapshot?.resources || [];
  const linkable = resources.filter(resource => (resource.link_roots || []).length > 0);
  function open(resource?: LargeResource) {
    const first = resource || linkable[0];
    if (!first) return;
    setDraft({name: first.id, source: '', target: '', environment: ''});
  }
  function chooseEnvironment(environment: string) {
    if (!draft) return;
    const next = linkCandidates(linkable, environment, draft.name);
    const name = next.some(item => item.id === draft.name) ? draft.name : (next[0]?.id || '');
    setDraft({...draft, environment, name});
  }
  async function submit(value: Draft) {
    const source = value.source.trim();
    if (!source || !value.name) return;
    await run(async () => {
      const send = async (replace: boolean) => value.target
        ? api.remoteLinkResource(value.target, value.name, source, replace)
        : api.largeResourceLink(value.name, source, replace);
      try {
        await send(false);
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && window.confirm(`${e.message}\n\n${t("是否替换现有的链接目标？")}`)) {
          await send(true);
        } else throw e;
      }
      if (!value.target) await reload();
      setDraft(null);
    }, t("已链接 {v0}", {v0: value.name}));
  }
  async function unlink(resource: LargeResource) {
    if (!window.confirm(t("解除 {v0} 的链接？源目录和文件不会被删除。", {v0: resource.title || resource.id}))) return;
    await run(async () => {await api.largeResourceUnlink(resource.id); await reload();}, t("已解除链接"));
  }
  const options = missingEnvironments(environments)
    .filter(option => linkCandidates(linkable, option.name).length > 0);
  const candidates = draft ? linkCandidates(linkable, draft.environment, draft.name) : [];
  const current = draft ? resources.find(resource => resource.id === draft.name) : undefined;
  return <div className="large-resources">
    <div className="settings-section-heading"><h3>{t("大型资源与模型权重")}</h3>
      <button className="subtle-button" disabled={busy || !linkable.length} onClick={() => open()}><Link size={15}/>{t("链接资源")}</button>
      <button className="subtle-button" disabled={busy} onClick={() => void run(reload, t("已刷新"))}><ArrowsClockwise size={15}/>{t("刷新")}</button></div>
    <p className="settings-note">{t("可把已有的本地目录或文件树外链到资源根目录，不复制字节；链接后仍可随时解除。")}</p>
    <p className="settings-note">{t("资源尚未安装时也可以先建立链接，安装过程会直接使用链接目录。")}</p>
    {!snapshot && !error && <p role="status">{t("正在读取资源…")}</p>}
    {!resources.length && snapshot && <p role="status">{t("当前算子库没有声明大型资源。")}</p>}
    <div className="large-resource-list">{resources.map(resource => <div className="large-resource" key={resource.id}>
      <div className="large-resource-heading"><strong>{resource.title || resource.id}</strong><code>{resource.id}</code>
        <span className={`large-resource-badge${resource.linked ? ' linked' : ''}`}>{stateLabel(resource)}</span>
        {resource.mode ? <span className="large-resource-mode">{resource.mode}</span> : null}
        <span className="large-resource-size">{bytes(resource.size_bytes)}</span></div>
      <dl>
        <div><dt>{t("资源根目录")}</dt><dd><code>{resource.root || t("未解析")}</code></dd></div>
        {resource.linked && resource.source ? <div><dt>{t("链接来源")}</dt><dd><code>{resource.source}</code></dd></div> : null}
        {resource.env ? <div><dt>{t("环境变量")}</dt><dd><code>{resource.env}</code></dd></div> : null}
        {resource.environments?.length ? <div><dt>{t("所属环境")}</dt><dd>{resource.environments.join(', ')}</dd></div> : null}
        <div><dt>{t("使用算子")}</dt><dd>{resource.used_by?.length ? resource.used_by.join(', ') : t("未被算子引用")}</dd></div>
      </dl>
      <div className="settings-form-actions">
        <button className="subtle-button" disabled={busy || !(resource.link_roots || []).length}
          onClick={() => open(resource)}><Link size={15}/>{t("链接已有目录")}</button>
        {resource.linked ? <button className="subtle-button" disabled={busy} onClick={() => void unlink(resource)}><LinkBreak size={15}/>{t("解除链接")}</button> : null}</div>
    </div>)}</div>
    {draft ? <div className="link-dialog" role="dialog" aria-label={t("链接资源")}>
      <h3>{t("链接资源")}</h3>
      <p className="settings-note">{t("仅支持链接数据库或模型权重目录，不复制字节；运行依赖请使用下载或安装。")}</p>
      <label><span>{t("执行位置")}</span>
        <select value={draft.target} onChange={event => setDraft({...draft, target: event.target.value})}>
          <option value="">{t("本地")}</option>
          {targets.map(remote => <option key={remote.id} value={remote.id}>{remote.name}</option>)}
        </select>
      </label>
      {!targets.length ? <p className="settings-note">{t("尚未配置服务器连接；在设置 → 服务器中添加后可在远端执行链接。")}</p> : null}
      <label><span>{t("缺失的环境")}</span>
        <select value={draft.environment} onChange={event => chooseEnvironment(event.target.value)}>
          <option value="">{t("全部环境")}</option>
          {options.map(option => <option key={option.name} value={option.name}>{option.title || option.name}（{option.status}）</option>)}
        </select>
      </label>
      <label><span>{t("缺失的权重或数据库")}</span>
        <select value={draft.name} disabled={!candidates.length} onChange={event => setDraft({...draft, name: event.target.value})}>
          {candidates.length ? candidates.map(resource =>
            <option key={resource.id} value={resource.id}>{resource.title || resource.id}</option>)
            : <option value="">{t("该环境下没有缺失的可链接资源")}</option>}
        </select>
      </label>
      <label><span>{t("目标绝对位置")}</span>
        <input value={draft.source} placeholder={current?.link_roots?.[0] || t('输入已有目录的绝对路径')}
          onChange={event => setDraft({...draft, source: event.target.value})}/>
      </label>
      <p className="settings-note">{t("填该资源在本机上的绝对路径；链接建好后 Operon 从资源根目录读取，字节不复制。")}</p>
      <p className="settings-note">{t("链接只作用于执行它的那台机器的本地文件系统，不会把远端文件映射到本机，也不复制字节。")}</p>
      {current?.link_roots?.length ?
        <p className="settings-note">{t("允许的链接根：")}{current.link_roots.join('；')}</p> : null}
      <div className="settings-form-actions">
        <button className="primary-button" disabled={busy || !draft.source.trim() || !draft.name} onClick={() => void submit(draft)}>{t("链接")}</button>
        <button className="subtle-button" disabled={busy} onClick={() => setDraft(null)}>{t("取消")}</button>
      </div>
    </div> : null}
    <div className="settings-feedback" aria-live="polite">{error ? <p className="field-error" role="alert">{error}</p> : <p role="status">{busy ? t("正在处理…") : message}</p>}</div>
  </div>;
}
