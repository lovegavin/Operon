import {useEffect, useRef, useState} from 'react';
import {request} from './api';
import {Modal} from './RouteDialogs';
import {PlanRunResults, planStatus} from './PlanRunResults';
import {PlanSummary} from './PlanPanel';
import {observePlan} from './planState';
import {t} from './i18n';
import type {Graph} from './types';
import type {RunPlan} from './planTypes';
import './planPanel.css';

type Preparation = {request_id: string; status: string; phase: string; error?: string; code?: string;
  prepared?: {plan: RunPlan; profile_id?: string | null}};
type Result = {run_id?: string; id?: string; status?: string; phase?: string; output?: string; error?: unknown};
type Entry = {body: {request_id: string; preparation_id: string; action: 'run' | 'export'; output?: string}; result?: Result};
const endpoint = '/api/v1/canvas-plans';
export function CanvasPlanDialog({graph, intent, onClose, onEnvironment, onAdvanced}: {graph: Graph; intent: 'run' | 'export' | 'history'; onClose: () => void; onEnvironment: () => void; onAdvanced: () => void}) {
  const snapshot = useRef(structuredClone(graph));
  const preparationId = useRef(`canvas-${crypto.randomUUID()}`);
  const actionId = useRef(`canvas-action-${crypto.randomUUID()}`);
  const [prepared, setPrepared] = useState<Preparation | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]), [selected, setSelected] = useState<Entry | null>(null);
  const [output, setOutput] = useState('');
  const [retry, setRetry] = useState(0);
  const submitted = useRef(false);
  useEffect(() => {
    if (intent === 'history') {
      const controller = new AbortController();
      request<Entry[]>(`${endpoint}/history`, undefined, {signal: controller.signal}).then(setEntries).catch(e => {if (!controller.signal.aborted) setError(e.message);});
      return () => controller.abort();
    }
    let started = false;
    return observePlan(async signal => {
      if (!started) {
        await request<Preparation>(`${endpoint}/prepare`, {graph: snapshot.current, request_id: preparationId.current}, {signal});
        started = true;
      }
      const next = await request<Preparation>(`${endpoint}/status?request_id=${encodeURIComponent(preparationId.current)}`, undefined, {signal});
      if (signal.aborted) return false;
      setPrepared(next);
      if (['failed', 'cancelled'].includes(next.status)) setError(next.error || t('安装失败'));
      return next.status === 'preparing';
    }, e => setError((e as Error).message));
  }, [intent, retry]);
  async function execute() {
    if (busy || intent === 'history') return;
    setBusy(true); setError('');
    try {
      const next = await request<Result>(`${endpoint}/execute`, {preparation_id: preparationId.current,
        request_id: actionId.current, action: intent, output: output.trim() || null});
      setResult(next);
    } catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  useEffect(() => {
    if (intent === 'run' && prepared?.status === 'ready' && !submitted.current) {
      submitted.current = true;
      void execute();
    }
  }, [prepared?.status]); // One action ID survives lost responses and retries.
  useEffect(() => {
    const id = selected?.body.request_id || actionId.current;
    if (!(result?.id || selected?.result?.id)) return;
    return observePlan(async signal => {
      const next = await request<Result>(`${endpoint}/outcome?request_id=${encodeURIComponent(id)}`, undefined, {signal});
      if (!signal.aborted) setResult(next);
      return ['queued', 'building', 'cancelling'].includes(next.status || '');
    }, e => setError((e as Error).message));
  }, [result?.id, selected]);
  const shown = result || selected?.result;
  async function cancelPreparation() {
    try {await request(`${endpoint}/cancel`, {request_id: preparationId.current});}
    catch (e) {setError((e as Error).message);}
  }
  async function retryPending(item: Entry) {
    setBusy(true); setError('');
    try {const next = await request<Result>(`${endpoint}/execute`, item.body); setResult(next);}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  return <Modal title={t(intent === 'run' ? '运行路线' : intent === 'export' ? '导出独立运行包' : '路线运行与导出记录')} onClose={onClose}>
    <div className="plan-panel">
      {intent === 'history' ? <div className="plan-history">{entries.map(item => <button key={item.body.request_id} aria-pressed={selected === item} onClick={() => {setSelected(item); setResult(null); setError('');}}><strong>{t(item.body.action === 'run' ? '运行路线' : '导出独立运行包')}</strong><small>{item.result?.run_id || item.result?.output || item.body.request_id}</small></button>)}</div>
        : <><h3>{snapshot.current.name}</h3>{prepared?.status === 'preparing' && <p role="status">{t('正在自动准备')} · {prepared.phase}</p>}
          {prepared?.prepared && <PlanSummary plan={prepared.prepared.plan}/>}
          {intent === 'export' && <label className="field"><span>{t('输出目录（留空自动创建）')}</span><input value={output} disabled={busy || !!result} onChange={e => setOutput(e.target.value)} placeholder="exports/…"/></label>}
          {prepared?.status === 'preparing' && <button className="subtle-button" onClick={() => void cancelPreparation()}>{t('取消准备')}</button>}
          {prepared?.status === 'ready' && !result && <button className="primary-button" disabled={busy} onClick={() => void execute()}>{t(busy ? '正在提交' : intent === 'run' ? '用原标识确认运行' : '导出独立运行包')}</button>}
          {prepared && ['failed', 'cancelled'].includes(prepared.status) && <><button className="subtle-button" onClick={onEnvironment}>{t('运行环境设置')}</button><button className="subtle-button" onClick={() => {preparationId.current = `canvas-${crypto.randomUUID()}`; submitted.current = false; setError(''); setPrepared(null); setRetry(n => n + 1);}}>{t('重新准备')}</button></>}
        </>}
      {error && <p role="alert" className="modal-error">{error}</p>}
      {prepared?.code && ['portable_tool_required', 'multi_host_plan_required'].includes(prepared.code) && <button className="subtle-button" onClick={onAdvanced}>{t('执行计划')}</button>}
      {intent === 'history' && selected && !shown && <button className="primary-button" disabled={busy} onClick={() => void retryPending(selected)}>{t('用原标识确认提交结果')}</button>}
      {shown?.run_id && <PlanRunResults key={shown.run_id} runId={shown.run_id}/>}
      {shown?.id && <><p role="status">{planStatus(shown.status || '')} · {shown.phase}</p>{shown.output && <p>{t('保存位置')} <code>{shown.output}</code></p>}{shown.error != null && <pre className="plan-log">{typeof shown.error === 'string' ? shown.error : JSON.stringify(shown.error)}</pre>}</>}
    </div>
  </Modal>;
}
