import {useEffect, useRef, useState} from 'react';
import {t} from './i18n';
import {planApi} from './planApi';
import {observePlan} from './planState';
import {planStatus} from './PlanRunResults';
import type {ExportReceipt, PlanBinding, PlanExportRequest, PlanUiState, RunPlan} from './planTypes';

export function PlanExportPanel({plan, binding, store, save}: {plan: RunPlan | null; binding: PlanBinding;
  store: PlanUiState | null; save: (value: PlanUiState) => Promise<PlanUiState>}) {
  const [manifest, setManifest] = useState<Partial<PlanExportRequest> | null>(null);
  const [selected, setSelected] = useState(''), [receipt, setReceipt] = useState<ExportReceipt | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [refresh, setRefresh] = useState(0);
  const controller = useRef(new AbortController());
  const entry = store?.exports.find(item => item.request.request_id === selected);
  useEffect(() => {const current = new AbortController(); controller.current = current; return () => current.abort();}, []);
  useEffect(() => {
    if (!entry) return;
    return observePlan(async signal => {
      const value = entry.export_id ? await planApi.exportDetails(entry.export_id, signal) : await planApi.exportLookup(entry.request.request_id, signal);
      if (signal.aborted) return false;
      setReceipt(value);
      return ['queued', 'building', 'cancelling'].includes(value.status);
    }, failure => setError((failure as Error).message));
  }, [selected, entry?.export_id, refresh]);
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('');
    try {await work();} catch (failure) {if (!controller.current.signal.aborted) setError((failure as Error).message);}
    finally {if (!controller.current.signal.aborted) setBusy(false);}
  }
  async function submit() {
    if (!plan || !store || !manifest?.output) return;
    await act(async () => {
      if (store.exports.length >= 20) throw Error(t('导出记录已满；原始提交记录不会被自动删除。'));
      const request: PlanExportRequest = {...manifest, plan: structuredClone(plan), source_root: manifest.source_root || binding.package_root,
        environment_store: manifest.environment_store || binding.environment_store, environments: manifest.environments || binding.environments,
        output: manifest.output!, request_id: `export-${crypto.randomUUID()}`};
      const next = await save({...store, exports: [{request}, ...store.exports]});
      setSelected(request.request_id); setReceipt(null);
      const value = await planApi.export(request, controller.current.signal);
      await save({...next, exports: next.exports.map(item => item.request.request_id === request.request_id ? {...item, export_id: value.id} : item)});
      setReceipt(value);
    });
  }
  return <section className="plan-export">
    <h3>{t('独立运行包')}</h3><p className="plan-note">{t('使用固定计划和资源清单构建。环境检查与重定位探测由共享导出服务执行。')}</p>
    {!plan && <p className="plan-note">{t('先编译或导入一份执行计划。')}</p>}
    <label className="field"><span>{t('导入导出资源清单')}</span><input type="file" accept=".json,application/json" disabled={busy || !plan} onChange={event => {
      const file = event.target.files?.[0]; event.target.value = '';
      if (file) void act(async () => {
        const value = JSON.parse(await file.text());
        if (!value || typeof value !== 'object' || Array.isArray(value) || !value.source_root || !value.environment_store || !value.environments) throw Error(t('导出清单必须包含程序目录、环境仓库和固定环境。'));
        const {plan: _plan, request_id: _key, ...rest} = value;
        void _plan; void _key;
        setManifest(rest); setSelected(''); setReceipt(null);
      });
    }}/></label>
    {manifest && <><div className="plan-fields"><label className="field"><span>{t('程序目录')}</span><input disabled={busy} value={manifest.source_root || ''} onChange={event => setManifest({...manifest, source_root: event.target.value})}/></label>
      <label className="field"><span>{t('输出目录')}</span><input disabled={busy} value={manifest.output || ''} onChange={event => setManifest({...manifest, output: event.target.value})}/></label></div>
      <p>{t('固定环境')} {Object.keys(manifest.environments || {}).length} · {t('代码实现')} {Object.keys(manifest.implementations || {}).length} · {t('附加文件')} {Object.keys(manifest.extra_files || {}).length}</p>
      <button className="primary-button" disabled={busy || !plan || !store || !manifest.output} onClick={() => void submit()}>{t('构建独立运行包')}</button></>}
    <h4>{t('导出记录')}</h4>
    <div className="plan-history">{store?.exports.map(item => <button key={item.request.request_id} aria-pressed={selected === item.request.request_id} onClick={() => {setSelected(item.request.request_id); setReceipt(null); setError('');}}><strong>{item.request.output}</strong><small>{item.request.request_id}</small></button>)}</div>
    {error && <p role="alert" className="modal-error">{error}</p>}
    {entry && <><p className="mono plan-request">{entry.request.request_id}</p><p>{receipt ? `${planStatus(receipt.status)} · ${receipt.phase}` : t('正在确认导出回执')}</p>
      {receipt?.status === 'complete' && <p>{t('已保存到')} <code>{receipt.output}</code></p>}
      {receipt?.status === 'unknown' && <p className="plan-note">{t('导出完成情况不明，请先检查输出与服务记录，不要更换标识重复构建。')}</p>}
      {receipt?.error != null && <pre className="plan-log">{typeof receipt.error === 'string' ? receipt.error : JSON.stringify(receipt.error, null, 2)}</pre>}
      <div className="plan-actions"><button className="subtle-button" disabled={busy} onClick={() => {setError(''); setRefresh(value => value + 1);}}>{t('核对导出回执')}</button>
        {!receipt && <button className="subtle-button" disabled={busy} onClick={() => void act(async () => {
          const result = await planApi.export(entry.request, controller.current.signal);
          setReceipt(result); setRefresh(value => value + 1);
        })}>{t('使用原标识重试导出')}</button>}
        {receipt && ['queued', 'building', 'cancelling'].includes(receipt.status) && <button className="subtle-button" disabled={busy} onClick={() => void act(async () => {setReceipt(await planApi.cancelExport(receipt.id, controller.current.signal)); setRefresh(value => value + 1);})}>{t('取消构建')}</button>}</div></>}
  </section>;
}
