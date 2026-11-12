import { useEffect, useRef, useState } from 'react';
import { Package, Trash, Power, ArrowCounterClockwise, ArrowClockwise } from '@phosphor-icons/react';
import { Modal } from './RouteDialogs';
import {AddOperators} from './AddOperators';
import {t, useLocale} from './i18n';
import {operatorText} from './operatorLocalization';
import { api } from './api';
import type { PluginOperation, PluginState } from './types';
import type { EnvironmentSnapshot } from './api';

export type LibraryTab = 'manage' | 'add';
export function PluginPanel({onClose, onChanged, initialTab = 'manage'}: {onClose: () => void; onChanged: () => Promise<void>; initialTab?: LibraryTab}) {
  const locale = useLocale();
  const [tab, setTab] = useState<LibraryTab>(initialTab);
  const [state, setState] = useState<PluginState>({generation: null, packages: [], descriptors: []});
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const [environments, setEnvironments] = useState<EnvironmentSnapshot | undefined>();
  const [environmentLogs, setEnvironmentLogs] = useState<Record<string, string>>({});
  const busy = pending || !!state.dependencies?.running;
  const file = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    let active = true;
    const loadEnvironments = () => api.environments().then(value => {if (active) setEnvironments(value);}).catch(() => {});
    void loadEnvironments();
    const timer = setInterval(loadEnvironments, 4000);
    return () => {active = false; clearInterval(timer);};
  }, []);
  useEffect(() => {
    mounted.current = true;
    api.plugins().then(value => {if (mounted.current) setState(value);}).catch(e => {if (mounted.current) setError(e.message);});
    return () => {mounted.current = false;};
  }, []);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {void api.plugins().then(value => {if (mounted.current) setState(value);}).catch(() => {});}, 1000);
    return () => clearInterval(timer);
  }, [busy]);
  const dependencyLabels = {unchecked: t("待检测"), checking: t("检测中"), installing: t("安装中"), passed: t("依赖就绪"), failed: t("依赖未就绪")};
  const environmentLabels: Record<string, string> = {missing: t("未安装"), stale: t("需要更新"), ready: t("已就绪"), failed: t("准备失败")};
  const environmentBusy = !!environments?.operations?.some(job => job.status === 'running');
  async function prepareEnvironments(names?: string[]) {
    setError('');
    try {
      const latest = await api.prepareEnvironments(names);
      if (mounted.current) setEnvironments(latest);
    } catch (e) {if (mounted.current) setError((e as Error).message);}
  }
  async function toggleEnvironmentLog(name: string) {
    if (Object.hasOwn(environmentLogs, name)) {
      setEnvironmentLogs(current => {const next = {...current}; delete next[name]; return next;});
      return;
    }
    try {
      const result = await api.environmentLog(name);
      if (mounted.current) setEnvironmentLogs(current => ({...current, [name]: result.text || t('暂无日志')}));
    } catch (e) {if (mounted.current) setError((e as Error).message);}
  }
  async function operate(begin: () => Promise<PluginOperation>) {
    setPending(true); setError(''); setMessage(t("正在扫描、校验并更新算子库…"));
    try {
      let operation = await begin();
      while (operation.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (!mounted.current) return;
        operation = await api.pluginOperation(operation.id);
      }
      if (operation.status === 'failed') throw Error(operation.error || t("插件操作失败"));
      const latest = await api.plugins();
      if (mounted.current) {setState(latest); setMessage(operation.result
        ? operation.result.updated.length ? t("算子库已更新，即刻可用。") : t("没有发现新文件或修改。")
        : latest.dependencies?.entries.some(entry => entry.status === 'failed') ? t("依赖检测完成，部分算子需要处理。") : t("已完成。"));}
      await onChanged();
    } catch (e) {if (mounted.current) {setError((e as Error).message); setMessage('');}}
    finally {if (mounted.current) setPending(false);}
  }
  return <Modal dismissDisabled={pending} title={t("算子库")} onClose={() => {if (!pending) onClose();}}>
    <nav className="library-management-tabs" aria-label={t('算子库管理')}>
      <button aria-pressed={tab === 'manage'} onClick={() => setTab('manage')}>{t('算子库管理')}</button>
      <button aria-pressed={tab === 'add'} onClick={() => setTab('add')}>{t('添加算子')}</button>
    </nav>
    <div className="plugin-panel-body">
      <input ref={file} hidden type="file" accept=".whl,.operon-library.zip" onChange={event => {
        const selected = event.target.files?.[0]; event.target.value = '';
        if (selected) void operate(() => api.installPlugin(selected));
      }}/>
      <div hidden={tab !== "manage"}>
      <div className="plugin-toolbar">
        {state.library_release && <span className="route-version" title={t("最近导入的算子库版本，独立于软件版本")}>{t("库 v")}{state.library_release.version}</span>}
        <button className="primary-button" disabled={busy} onClick={() => void operate(api.refreshPlugins)}><ArrowClockwise size={16} className={pending ? 'spin' : ''}/>{t("刷新算子库")}</button>
        <button className="subtle-button" disabled={pending || state.dependencies?.running} onClick={() => void operate(api.repairDependencies)}><ArrowClockwise size={16}/>{state.dependencies?.running ? t("准备环境…") : t("修复依赖")}</button>
      </div>
      <div className="plugin-packages">
        {!state.packages.length && <div className="modal-empty"><Package size={30}/><p>{t("尚未安装算子包")}</p></div>}
        {state.packages.map(item => <article className="plugin-package" key={item.name}>
          <div><strong>{item.title || item.name}</strong><span className="route-version">v{item.version}</span>
            <p>{item.name} · {item.source_managed ? t("本地算子") : item.origin === 'bundled' ? t("预装") : t("已安装")} · {item.enabled === false ? t("已禁用") : t("已启用")}</p>
            <details><summary>{state.descriptors.filter(d => d.distribution === item.name).length} {t("个算子 / Reader")}</summary>
              {state.descriptors.filter(d => d.distribution === item.name).map(d => {
                const dependency = state.dependencies?.entries.find(entry => entry.id === d.id);
                return <div key={d.id}><p>{(d.localization && operatorText(d.localization, locale).title) ?? d.title} <small>{d.resources?.memory_modes.map(mode => ({full: t("完整矩阵"), stream: t("分块流式"), disk: t("分块落盘")}[mode] || mode)).join(' · ')}{dependency && ` · ${dependencyLabels[dependency.status]}`}</small></p>
                  {dependency?.execution?.mode === 'isolated' && <small title={dependency.execution.reason}>{t("独立依赖进程")}</small>}
                  {dependency?.status === 'failed' && <pre className="modal-error">{dependency.error}</pre>}</div>;
              })}
            </details>
          </div>
          <div className="plugin-actions">
          <button className="icon-button" title={`${item.enabled === false ? t("启用") : t("禁用")} ${item.name}`} aria-label={`${item.enabled === false ? t("启用") : t("禁用")} ${item.name}`} disabled={busy} onClick={() => void operate(() => api.managePlugin(item.name, item.enabled === false ? 'enable' : 'disable'))}><Power size={17}/></button>
          <button className="icon-button" title={t("移除 {v0}", {v0: item.name})} aria-label={t("移除 {v0}", {v0: item.name})} disabled={busy} onClick={() => void operate(() => api.removePlugin(item.name))}><Trash size={17}/></button>
          </div>
        </article>)}
        {state.bundled_packages?.filter(item => !state.packages.some(p => p.name === item.name && (p.origin === 'bundled' || p.source_managed))).map(item =>
          <article className="plugin-package" key={'restore-' + item.name}><div><strong>{item.title || item.name}</strong><p>{t("可恢复预装版本 v")}{item.version}</p></div>
            <button className="subtle-button" disabled={busy} onClick={() => void operate(() => api.managePlugin(item.name, 'restore'))}><ArrowCounterClockwise size={15}/>{t("恢复")}</button></article>)}
      </div>
      </div>
      <section className="plugin-environments" hidden={!environments || (!Object.keys(environments.environments).length && environments.manifest.present)}>
        <div className="plugin-toolbar">
          <strong>{t('隔离环境')}</strong>
          <button className="subtle-button" disabled={pending || environmentBusy} onClick={() => void prepareEnvironments()}>
            <ArrowClockwise size={16} className={environmentBusy ? 'spin' : ''}/>{t('准备缺失环境')}
          </button>
        </div>
        <p className="helper">{t('隔离环境由当前算子库声明，缺少时算子无法执行。')}</p>
        {environments && !environments.manifest.present && <p className="helper">{t('当前算子库未声明隔离环境，请导入 8.0.6 或更新的算子库。')}</p>}
        {Object.values(environments?.environments ?? {}).map(item => <article className="plugin-package" key={item.name}>
          <div>
            <strong>{item.name}</strong><span className="route-version">Python {item.python}</span>
            <p>{environmentLabels[item.status]}{item.used_by.length ? ` · ${t('{n} 个算子', {n: item.used_by.length})}` : ''}</p>
            {item.status === 'failed' && item.error && <pre className="modal-error">{item.error}</pre>}
            {Object.hasOwn(environmentLogs, item.name) && <pre className="environment-log">{environmentLogs[item.name]}</pre>}
          </div>
          <div className="plugin-actions">
            <button className="subtle-button" disabled={pending || environmentBusy}
              onClick={() => void prepareEnvironments([item.name])}>
              {item.status === 'ready' ? t('重新准备') : item.status === 'failed' ? t('重试') : t('准备')}
            </button>
            <button className="subtle-button" onClick={() => void toggleEnvironmentLog(item.name)}>
              {Object.hasOwn(environmentLogs, item.name) ? t('隐藏日志') : t('日志')}
            </button>
          </div>
        </article>)}
      </section>
      <div hidden={tab !== 'add'}><AddOperators state={state} busy={busy} onPackage={() => file.current?.click()}
        onRefresh={() => void operate(api.refreshPlugins)} onChanged={onChanged} onPending={setPending} onError={setError} onMessage={setMessage}/></div>
    </div>
    {(message || error) && <div className="library-operation-feedback">
      {message && <p role="status" className="plugin-status">{message}</p>}
      {error && <p role="alert" className="modal-error">{error}</p>}
    </div>}
    <footer><span className="modal-spacer"/><button className="subtle-button" disabled={pending} onClick={onClose}>{t("完成")}</button></footer>
  </Modal>;
}
