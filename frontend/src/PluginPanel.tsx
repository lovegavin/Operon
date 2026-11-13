import { useEffect, useRef, useState } from 'react';
import { ArrowClockwise } from '@phosphor-icons/react';
import { Modal } from './RouteDialogs';
import {AddOperators} from './AddOperators';
import {LegacyLibraryAlert, LibrarySetupGuide} from './LibraryNotices';
import {isLegacyLibraryError, isLibraryBundleFile, libraryInstallSummary, refreshedCount} from './libraryImport';
import {t} from './i18n';
import { api, ApiError } from './api';
import type { LibraryInstallResult, LibraryList, LibraryRecord, PluginOperation, PluginState } from './types';

/** 5.1.0 list rows carry the operator/Reader split directly. */
function recordCounts(record: LibraryRecord) {
  return t('{operators} 个算子 · {readers} 个 Reader', {operators: record.operators, readers: record.readers});
}

export type LibraryTab = 'manage' | 'add';
export function PluginPanel({onClose, onChanged, initialTab = 'manage'}: {onClose: () => void; onChanged: () => Promise<void>; initialTab?: LibraryTab}) {
  const [tab, setTab] = useState<LibraryTab>(initialTab);
  const [state, setState] = useState<PluginState>({generation: null, packages: [], descriptors: []});
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const [legacy, setLegacy] = useState('');
  const [libraries, setLibraries] = useState<LibraryList | null>(null);
  const busy = pending || !!state.dependencies?.running;
  const file = useRef<HTMLInputElement>(null);
  const libraryLabel = useRef('');
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    api.plugins().then(value => {if (mounted.current) setState(value);}).catch(e => {if (mounted.current) setError(e.message);});
    void loadLibraries();
    return () => {mounted.current = false;};
  }, []);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {void api.plugins().then(value => {if (mounted.current) setState(value);}).catch(() => {});}, 1000);
    return () => clearInterval(timer);
  }, [busy]);
  async function loadLibraries() {
    try {
      const list = await api.libraries();
      if (mounted.current) setLibraries(list);
    } catch { /* Older backends lack /api/libraries; the plugin-state fallback still shows one library. */ }
  }
  async function runLibraryAction(begin: () => Promise<unknown>, success: string) {
    if (pending) return;
    setPending(true); setError(''); setMessage(''); setLegacy('');
    try {
      await begin();
      const latest = await api.plugins().catch(() => null);
      if (!mounted.current) return;
      if (latest) setState(latest);
      await loadLibraries();
      if (mounted.current) setMessage(success);
      await onChanged();
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      if (mounted.current) setPending(false);
    }
  }
  function removeLibrary(record: LibraryRecord) {
    const question = t('确定删除算子库 {name}？此操作不可撤销。', {name: record.name});
    if (typeof window !== 'undefined' && !window.confirm(question)) return;
    void runLibraryAction(() => api.deleteLibrary(record.name), t('已删除算子库 {name}。', {name: record.name}));
  }
  async function operate(begin: () => Promise<PluginOperation | LibraryInstallResult>, options?: {library?: boolean}) {
    setPending(true); setError(''); setMessage(t("正在扫描、校验并更新算子库…")); setLegacy('');
    try {
      const started = await begin();
      let result: PluginOperation['result'];
      if ('status' in started) {
        let operation = started;
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
        result = operation.result;
      } else {
        // A bundled 5.1.0 install returns its summary synchronously.
        result = started;
      }
      const latest = await api.plugins();
      if (mounted.current) {
        setState(latest);
        const summary = options?.library ? libraryInstallSummary(result, latest) : null;
        if (summary) setMessage(t("已导入算子库 v{version}：{descriptors} 个算子 / Reader。", summary));
        else {
          const updated = refreshedCount(result);
          setMessage(result
            ? updated ? t("算子库已更新，即刻可用。") : t("没有发现新文件或修改。")
            : latest.dependencies?.entries.some(entry => entry.status === 'failed') ? t("依赖检测完成，部分算子需要处理。") : t("已完成。"));
        }
      }
      await loadLibraries();
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
  // Older backends may not expose /api/libraries yet; the plugin state still describes the installed library.
  const fallback: LibraryRecord[] = state.library_release ? [{
    name: state.library_release.name || 'operon-library',
    library_version: state.library_release.version,
    sha256: state.library_release.sha256,
    installed_at: state.library_release.installed_at || '',
    packages: state.packages.length,
    descriptors: state.descriptors.length,
    operators,
    readers,
  }] : [];
  const records = libraries?.libraries.length ? libraries.libraries : fallback;
  return <Modal dismissDisabled={pending} title={t("算子库")} onClose={() => {if (!pending) onClose();}}>
    <nav className="library-management-tabs" aria-label={t('算子库管理')}>
      <button aria-pressed={tab === 'manage'} onClick={() => setTab('manage')}>{t('算子库管理')}</button>
      <button aria-pressed={tab === 'add'} onClick={() => setTab('add')}>{t('添加算子')}</button>
    </nav>
    <div className="plugin-panel-body">
      <input ref={file} hidden type="file" accept=".operon-library.zip" onChange={event => {
        const selected = event.target.files?.[0]; event.target.value = '';
        // 5.1.0 bundles carry an optional label; wheels still go through the plugin install endpoint.
        if (!selected) return;
        const bundle = isLibraryBundleFile(selected.name);
        const label = libraryLabel.current.trim();
        libraryLabel.current = '';
        void operate(bundle ? () => api.installLibrary(selected, label || undefined) : () => api.installPlugin(selected), {library: bundle});
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
        {!records.length && <LibrarySetupGuide busy={busy} onImport={() => {libraryLabel.current = ''; setTab('add'); file.current?.click();}}/>}
        {records.map(record =>
          <article className="plugin-package library-record" key={record.name}>
            <div>
              <strong>{record.name || t("算子库")}</strong><span className="route-version">v{record.library_version}</span>
              <p>{recordCounts(record)}</p>
              <p>{t('{packages} 个包', {packages: record.packages})}</p>
              {record.installed_at && <p>{t('导入时间：{time}', {time: record.installed_at})}</p>}
            </div>
            <div className="library-record-actions">
              <button className="subtle-button library-delete" disabled={busy} onClick={() => removeLibrary(record)}>{t('删除算子库')}</button>
            </div>
          </article>)}
        {records.length > 0 && <p className="operator-install-note">{t('算子库可同时安装多个，内部算子不再单独管理。')}</p>}
      </div>
      </div>
      <div hidden={tab !== "add"}><AddOperators busy={busy} onPackage={name => {libraryLabel.current = name ?? ''; file.current?.click();}}
        onChanged={onChanged} onPending={setPending} onError={setError} onMessage={setMessage}/></div>
    </div>
    {legacy && <LegacyLibraryAlert message={legacy} onChoose={() => {libraryLabel.current = ''; setLegacy(''); setTab('add'); file.current?.click();}}/>}
    {(message || error) && <div className="library-operation-feedback">
      {message && <p role="status" className="plugin-status">{message}</p>}
      {error && <p role="alert" className="modal-error">{error}</p>}
    </div>}
    <footer><span className="modal-spacer"/><button className="subtle-button" disabled={pending} onClick={onClose}>{t("完成")}</button></footer>
  </Modal>;
}
