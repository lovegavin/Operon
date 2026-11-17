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

export function LargeResources() {
  const [snapshot, setSnapshot] = useState<LargeResourceSnapshot | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  useEffect(() => {
    let alive = true;
    api.largeResources().then(value => {if (alive) setSnapshot(value);})
      .catch(e => {if (alive) setError(e instanceof Error ? e.message : String(e));});
    return () => {alive = false;};
  }, []);
  async function run(action: () => Promise<void>, success: string) {
    setBusy(true); setError(''); setMessage('');
    try {await action(); setMessage(success);}
    catch (e) {setError(e instanceof Error ? e.message : String(e));}
    finally {setBusy(false);}
  }
  async function reload() {setSnapshot(await api.largeResources());}
  async function link(resource: LargeResource) {
    const answer = window.prompt(t("输入已有目录的绝对路径，链接后不会复制文件："), resource.link_roots?.[0] || '');
    if (answer === null || !answer.trim()) return;
    const source = answer.trim();
    await run(async () => {
      try {
        await api.largeResourceLink(resource.id, source);
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && window.confirm(`${e.message}\n\n${t("是否替换现有的链接目标？")}`)) {
          await api.largeResourceLink(resource.id, source, true);
        } else throw e;
      }
      await reload();
    }, t("已链接 {v0}", {v0: resource.title || resource.id}));
  }
  async function unlink(resource: LargeResource) {
    if (!window.confirm(t("解除 {v0} 的链接？源目录和文件不会被删除。", {v0: resource.title || resource.id}))) return;
    await run(async () => {await api.largeResourceUnlink(resource.id); await reload();}, t("已解除链接"));
  }
  const resources = snapshot?.resources || [];
  return <div className="large-resources">
    <div className="settings-section-heading"><h3>{t("大型资源与模型权重")}</h3>
      <button className="subtle-button" disabled={busy} onClick={() => void run(reload, t("已刷新"))}><ArrowsClockwise size={15}/>{t("刷新")}</button></div>
    <p className="settings-note">{t("可把已有的本地目录或文件树外链到资源根目录，不复制字节；链接后仍可随时解除。")}</p>
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
        <div><dt>{t("使用算子")}</dt><dd>{resource.used_by?.length ? resource.used_by.join(', ') : t("未被算子引用")}</dd></div>
      </dl>
      <div className="settings-form-actions">
        <button className="subtle-button" disabled={busy} onClick={() => void link(resource)}><Link size={15}/>{t("链接已有目录")}</button>
        {resource.linked ? <button className="subtle-button" disabled={busy} onClick={() => void unlink(resource)}><LinkBreak size={15}/>{t("解除链接")}</button> : null}</div>
    </div>)}</div>
    <div className="settings-feedback" aria-live="polite">{error ? <p className="field-error" role="alert">{error}</p> : <p role="status">{busy ? t("正在处理…") : message}</p>}</div>
  </div>;
}
