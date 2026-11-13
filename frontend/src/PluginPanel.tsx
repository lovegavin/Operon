import { useEffect, useRef, useState } from 'react';
import { ArrowClockwise } from '@phosphor-icons/react';
import { Modal } from './RouteDialogs';
import {AddOperators} from './AddOperators';
import {LegacyLibraryAlert, LibrarySetupGuide} from './LibraryNotices';
import {isLegacyLibraryError, isLibraryBundleFile, libraryInstallSummary, refreshedCount} from './libraryImport';
import {t} from './i18n';
import { api, ApiError } from './api';
import type { PluginOperation, PluginState } from './types';

export type LibraryTab = 'manage' | 'add';
export function PluginPanel({onClose, onChanged, initialTab = 'manage'}: {onClose: () => void; onChanged: () => Promise<void>; initialTab?: LibraryTab}) {
  const [tab, setTab] = useState<LibraryTab>(initialTab);
  const [state, setState] = useState<PluginState>({generation: null, packages: [], descriptors: []});
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const [legacy, setLegacy] = useState('');
  const busy = pending || !!state.dependencies?.running;
  const file = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
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
  async function operate(begin: () => Promise<PluginOperation>, options?: {library?: boolean}) {
    setPending(true); setError(''); setMessage(t("正在扫描、校验并更新算子库…")); setLegacy('');
    try {
      let operation = await begin();
      while (operation.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (!mounted.current) return;
        operation = await api.pluginOperation(operation.id);
      }
      if (operation.status === 'failed') {
        const failure = operation.error || t("插件操作失败");
        if (isLegacyLibraryError(failure)) {if (mounted.current) setLegacy(failure); return;}
        throw Error(failure);
      }
      const latest = await api.plugins();
      if (mounted.current) {
        setState(latest);
        const summary = options?.library ? libraryInstallSummary(operation.result, latest) : null;
        if (summary) setMessage(t("已导入算子库 v{version}：{descriptors} 个算子 / Reader。", summary));
        else {
          const updated = refreshedCount(operation.result);
          setMessage(operation.result
            ? updated ? t("算子库已更新，即刻可用。") : t("没有发现新文件或修改。")
            : latest.dependencies?.entries.some(entry => entry.status === 'failed') ? t("依赖检测完成，部分算子需要处理。") : t("已完成。"));
        }
      }
      await onChanged();
    } catch (e) {
      if (!mounted.current) return;
      const failure = (e as Error).message;
      // A legacy 8.x bundle is a rejection, not a generic failure: keep its text and add the 5.0.0 hint.
      if (isLegacyLibraryError(failure, (e as ApiError).status)) {setLegacy(failure); setError(''); setMessage('');}
      else {setError(failure); setMessage('');}
    }
    finally {if (mounted.current) setPending(false);}
  }
  const operators = state.descriptors.filter(item => item.kind === 'operator').length;
  const readers = state.descriptors.filter(item => item.kind === 'reader').length;
  return <Modal dismissDisabled={pending} title={t("算子库")} onClose={() => {if (!pending) onClose();}}>
    <nav className="library-management-tabs" aria-label={t('算子库管理')}>
      <button aria-pressed={tab === 'manage'} onClick={() => setTab('manage')}>{t('算子库管理')}</button>
      <button aria-pressed={tab === 'add'} onClick={() => setTab('add')}>{t('添加算子')}</button>
    </nav>
    <div className="plugin-panel-body">
      <input ref={file} hidden type="file" accept=".operon-library.zip" onChange={event => {
        const selected = event.target.files?.[0]; event.target.value = '';
        // 5.0.0 library bundles are named operon-library-v0.0.x.operon-library.zip; wheels are the only non-bundle input.
        if (selected) void operate(() => api.installPlugin(selected), {library: isLibraryBundleFile(selected.name)});
      }}/>
      <div hidden={tab !== "manage"}>
      <div className="plugin-toolbar">
        {state.library_release && <>
          <span className="route-version" title={t("最近导入的算子库版本，独立于软件版本")}>{t("算子库 v")}{state.library_release.version}</span>
          <span className="plugin-status">{t('{operators} 个算子 · {readers} 个 Reader', {operators, readers})}</span>
        </>}
        <button className="primary-button" disabled={busy} onClick={() => void operate(api.refreshPlugins)}><ArrowClockwise size={16} className={pending ? 'spin' : ''}/>{t("刷新算子库")}</button>
        <button className="subtle-button" title={t("修复缺失依赖，并按需安装算子库声明的隔离环境")} disabled={pending || state.dependencies?.running} onClick={() => void operate(api.repairDependencies)}><ArrowClockwise size={16}/>{state.dependencies?.running ? t("修复中…") : t("修复依赖")}</button>
      </div>
      <div className="plugin-packages">
        {!state.library_release && <LibrarySetupGuide busy={busy} onImport={() => {setTab('add'); file.current?.click();}}/>}
        {state.library_release && <article className="plugin-package library-record">
          <div>
            <strong>{t("算子库")}</strong><span className="route-version">v{state.library_release.version}</span>
            <p>{t('{operators} 个算子 · {readers} 个 Reader', {operators, readers})}</p>
            {state.library_release.installed_at && <p>{t('导入时间：{time}', {time: state.library_release.installed_at})}</p>}
            <p>{t('算子库以整体安装与切换，内部算子不再单独管理。')}</p>
          </div>
        </article>}
      </div>
      </div>
      <div hidden={tab !== "add"}><AddOperators busy={busy} onPackage={() => file.current?.click()}
        onChanged={onChanged} onPending={setPending} onError={setError} onMessage={setMessage}/></div>
    </div>
    {legacy && <LegacyLibraryAlert message={legacy} onChoose={() => {setLegacy(''); setTab('add'); file.current?.click();}}/>}
    {(message || error) && <div className="library-operation-feedback">
      {message && <p role="status" className="plugin-status">{message}</p>}
      {error && <p role="alert" className="modal-error">{error}</p>}
    </div>}
    <footer><span className="modal-spacer"/><button className="subtle-button" disabled={pending} onClick={onClose}>{t("完成")}</button></footer>
  </Modal>;
}
