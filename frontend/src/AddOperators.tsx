import {useEffect, useRef, useState} from 'react';
import {FileArrowUp, Package, Plus, Stack} from '@phosphor-icons/react';
import {api} from './api';
import {normalizeGraph} from './graph';
import {isRouteArchiveFile, isRouteLibraryFile} from './libraryImport';
import {isWorkflowBundle, ROUTE_FILE_ACCEPT} from './workflowFiles';
import type {WorkflowSummary} from './types';
import {t} from './i18n';

export function AddOperators({busy, onPackage, onChanged, onPending, onError, onMessage}: {
  busy: boolean; onPackage: () => void;
  onChanged: () => Promise<void>; onPending: (value: boolean) => void;
  onError: (value: string) => void; onMessage: (value: string) => void;
}) {
  const [routes, setRoutes] = useState<WorkflowSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const file = useRef<HTMLInputElement>(null);
  const collection = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    api.workflows().then(items => {if (active) setRoutes(items);}).catch(error => {if (active) onError(error.message);})
      .finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, []);
  async function importCollection(file: File) {
    onPending(true); onError(''); onMessage('');
    try {
      const imported = await api.importRouteCollection(file);
      const names = imported.names.join(', ');
      onMessage(names
        ? t('已导入 {count} 条路线：{names}', {count: imported.count, names})
        : t('已导入 {count} 条路线。', {count: imported.count}));
      if (imported.failed.length) onError(t('{count} 条路线未导入：{reason}', {count: imported.failed.length, reason: imported.failed[0].error}));
    } catch (error) {
      // Pin mismatches name the operator id and expected/actual code_sha: keep the server text verbatim.
      onError((error as Error).message);
    } finally {
      try {setRoutes(await api.workflows()); await onChanged();}
      catch (error) {onError((error as Error).message);}
      onPending(false);
    }
  }
  async function register(files?: File[]) {
    const chosen = files ?? [];
    // A 5.0.0 route-library collection dropped on the single-route picker still uses its own endpoint.
    if (chosen.length === 1 && isRouteLibraryFile(chosen[0].name)) {await importCollection(chosen[0]); return;}
    onPending(true); onError(''); onMessage('');
    const containers = chosen.filter(item => isRouteArchiveFile(item.name));
    if (containers.length) {
      if (chosen.length !== 1) {
        onError(t('路线压缩包请单独上传。'));
        onPending(false);
        return;
      }
      try {
        const imported = await api.importRouteArchive(containers[0]);
        if (imported.failed.length) {
          onError(t('已添加 {count} 条路线；{failed} 条未导入。请先导入与路线同版本的算子库后重试：{reason}', {
            count: imported.routes.length, failed: imported.failed.length,
            reason: imported.failed[0].error,
          }));
        } else {
          onMessage(t('路线算子已添加，即刻可用。'));
        }
      } catch (error) {
        onError(t('路线未添加：{reason} 请先导入与路线同版本的算子库后重试。', {reason: (error as Error).message}));
      } finally {
        try {setRoutes(await api.workflows()); await onChanged();}
        catch (error) {onError((error as Error).message);}
        onPending(false);
      }
      return;
    }
    // Save each imported graph once; failures leave it available for retry.
    const saved: string[] = [];
    try {
      if (files) for (const item of chosen) {
        const graph = normalizeGraph(isWorkflowBundle(item.name)
          ? await api.importWorkflow(item) : JSON.parse(await item.text()));
        saved.push((await api.saveWorkflow(graph)).id);
      }
      await api.registerRoutes(files ? saved : selected);
      setSelected([]);
      onMessage(t('路线算子已添加，即刻可用。'));
    } catch (error) {onError(t('路线未添加：{reason} 请先导入与路线同版本的算子库后重试。', {reason: (error as Error).message})); if (saved.length) setSelected(saved);}
    finally {
      try {setRoutes(await api.workflows()); await onChanged();}
      catch (error) {onError((error as Error).message);}
      onPending(false);
    }
  }
  const visible = routes;
  return <div className="add-operators">
    <h2 className="operator-section-heading">{t('普通算子与 Reader')}</h2>
    <section className="operator-install-card">
      <div className="operator-install-heading"><span><Package size={24}/></span><div><h3>{t('导入算子库')}</h3><code>.operon-library.zip</code></div>
        <button className="primary-button" disabled={busy} onClick={() => onPackage()}><FileArrowUp size={16}/>{t('导入算子库')}</button></div>
    </section>
    <h2 className="operator-section-heading">{t('路线算子')}</h2>
    <section className="operator-install-card">
      <div className="operator-install-heading"><span><Stack size={24}/></span><div><h3>{t('导入路线库')}</h3><code>.zip（routes/*.operon.zip）</code></div>
        <div className="operator-install-actions">
          <button className="subtle-button" disabled={busy} onClick={() => file.current?.click()}><FileArrowUp size={16}/>{t('导入路线文件')}</button>
          <button className="subtle-button" disabled={busy} onClick={() => collection.current?.click()}><FileArrowUp size={16}/>{t('导入路线库')}</button>
        </div></div>
      <input hidden ref={file} type="file" multiple accept={ROUTE_FILE_ACCEPT} onChange={event => {
        const files = Array.from(event.target.files || []); event.target.value = '';
        if (files.length) void register(files);
      }}/>
      <input hidden ref={collection} type="file" accept=".zip" aria-label={t('导入路线库')} onChange={event => {
        const file = event.target.files?.[0]; event.target.value = '';
        if (!file) return;
        if (!isRouteLibraryFile(file.name)) {onError(t('路线库请选择 .zip 集合包（包含 routes/*.operon.zip）。')); return;}
        void importCollection(file);
      }}/>
      <p className="operator-install-note">{t('路线库包：.zip 集合包')} · {t('包含 routes/*.operon.zip，需与算子库同一版本。')}</p>
      <div className="saved-operator-routes">
        <div className="add-route-list">
          {!visible.length && <div className="modal-empty"><Stack size={24}/><p>{loading ? t('正在读取保存的路线…') : t('暂无已保存路线')}</p></div>}
          {visible.map(route => <label className={`workflow-choice ${selected.includes(route.id) ? 'checked' : ''}`} key={route.id}>
            <input type="checkbox" disabled={busy || loading} checked={selected.includes(route.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, route.id] : ids.filter(id => id !== route.id))}/>
            <span className="workflow-choice-text"><strong>{route.name}</strong><small>{t('{count} 个节点', {count: route.nodes})} · v{route.version}</small></span>
            {route.registered_version && <span className="route-version">{route.registered_version === route.version ? t('已注册') : t('可更新')}</span>}
          </label>)}
        </div>
        <div className="add-route-actions"><span>{selected.length > 0 && t('已选 {count} 条', {count: selected.length})}</span><button className="primary-button" disabled={busy || loading || !selected.length} onClick={() => void register()}><Plus size={16}/>{t('添加到算子库')}</button></div>
      </div>
    </section>
  </div>;
}
