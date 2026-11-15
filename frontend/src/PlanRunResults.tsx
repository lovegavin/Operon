import {useEffect, useRef, useState} from 'react';
import {ArrowClockwise, Stop} from '@phosphor-icons/react';
import {ApiError, downloadBlob} from './api';
import {t} from './i18n';
import {planApi} from './planApi';
import {observePlan, terminalPlan} from './planState';
import {createDesktopHost} from './host';
import {openNativeArtifact} from './host/artifacts';
import type {PlanArtifact, PlanAttempt, PlanEvent, PlanFile, PlanFilePreview, PlanPage, PlanReceipt} from './planTypes';

export function PlanRunResults({runId}: {runId: string}) {
  const [receipt, setReceipt] = useState<PlanReceipt | null>(null);
  const [events, setEvents] = useState<PlanEvent[]>([]);
  const [attempts, setAttempts] = useState<PlanPage<PlanAttempt, 'attempts'> | null>(null);
  const [artifacts, setArtifacts] = useState<PlanPage<PlanArtifact, 'artifacts'> | null>(null);
  const [error, setError] = useState(''), [refresh, setRefresh] = useState(0), [busy, setBusy] = useState(false);
  const [gap, setGap] = useState<number | null>(null);
  const cursor = useRef(0), attemptCursor = useRef(''), artifactCursor = useRef(''), controller = useRef(new AbortController());
  useEffect(() => {
    const current = new AbortController(); controller.current = current;
    return () => current.abort();
  }, []);
  useEffect(() => observePlan(async signal => {
    const next = await planApi.details(runId, signal);
    const [newAttempts, newArtifacts] = await Promise.all([
      planApi.attempts(runId, attemptCursor.current, signal), planApi.artifacts(runId, artifactCursor.current, signal),
    ]);
    if (signal.aborted) return false;
    setReceipt(next); setAttempts(newAttempts); setArtifacts(newArtifacts);
    if (gap === null) {
      try {
        const page = await planApi.events(runId, cursor.current, signal);
        if (signal.aborted) return false;
        cursor.current = page.next_cursor;
        setEvents(current => [...new Map([...current, ...page.events].map(item => [item.cursor, item])).values()].slice(-100));
        // A terminal run can still have multiple retained pages. Drain one per
        // bounded observation cycle rather than dropping the final events.
        if (page.has_more) return true;
      } catch (failure) {
        const floor = (failure as ApiError).details as {details?: {floor?: number}} | undefined;
        if ((failure as ApiError).code === 'cursor_expired' && typeof floor?.details?.floor === 'number') setGap(floor.details.floor);
        else throw failure;
      }
    }
    return !terminalPlan(next.state);
  }, failure => setError((failure as Error).message)), [runId, refresh, gap]);
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('');
    try {await work();} catch (failure) {if (!controller.current.signal.aborted) setError((failure as Error).message);}
    finally {if (!controller.current.signal.aborted) setBusy(false);}
  }
  return <section className="plan-results">
    <div className="plan-section-title"><h3>{t('任务状态')} · {receipt ? planStatus(receipt.state) : t('读取中…')}</h3>
      <button className="icon-button" aria-label={t('刷新计划状态')} onClick={() => {setError(''); setRefresh(value => value + 1);}}><ArrowClockwise size={16}/></button>
      <button className="subtle-button" disabled={busy || !receipt || terminalPlan(receipt.state)} onClick={() => void act(async () => {setReceipt(await planApi.cancel(runId, controller.current.signal)); setRefresh(value => value + 1);})}><Stop size={15}/>{t('取消任务')}</button></div>
    <p className="mono plan-request">{runId}</p>
    {error && <p className="modal-error" role="alert">{error}</p>}
    {gap !== null && <p role="status" className="plan-note">{t('部分早期事件已过期。任务状态仍来自服务。')}
      <button className="text-button" onClick={() => {cursor.current = gap; setEvents([]); setGap(null);}}>{t('从保留记录继续')}</button></p>}
    <details><summary>{t('状态变更')}</summary><ol className="plan-events">{events.map(item => <li key={item.cursor}><span>{item.kind}</span><span>{item.unit_id || ''}</span><time>{item.created_at}</time></li>)}</ol></details>
    <h4>{t('执行尝试')}</h4>
    {!attempts?.attempts.length && <p className="plan-note">{t('尚无执行尝试')}</p>}
    {attempts?.attempts.map(item => <AttemptLog key={item.attempt_id} runId={runId} attempt={item}/>)}
    <div className="plan-actions"><button className="text-button" disabled={!attemptCursor.current || busy} onClick={() => {attemptCursor.current = ''; setRefresh(value => value + 1);}}>{t('首页')}</button>
      <button className="text-button" disabled={!attempts?.has_more || busy} onClick={() => {attemptCursor.current = attempts!.next_cursor; setRefresh(value => value + 1);}}>{t('下一页')}</button></div>
    <h4>{t('已提交产物')}</h4>
    {!artifacts?.artifacts.length && <p className="plan-note">{t('尚无已提交产物')}</p>}
    {artifacts?.artifacts.map(item => <ArtifactFiles key={`${item.unit_id}/${item.artifact_id}`} runId={runId} artifact={item}/>)}
    <div className="plan-actions"><button className="text-button" disabled={!artifactCursor.current || busy} onClick={() => {artifactCursor.current = ''; setRefresh(value => value + 1);}}>{t('首页')}</button>
      <button className="text-button" disabled={!artifacts?.has_more || busy} onClick={() => {artifactCursor.current = artifacts!.next_cursor; setRefresh(value => value + 1);}}>{t('下一页')}</button></div>
  </section>;
}

function AttemptLog({runId, attempt}: {runId: string; attempt: PlanAttempt}) {
  const [open, setOpen] = useState(false), [text, setText] = useState(''), [error, setError] = useState('');
  const [eof, setEof] = useState(false), [available, setAvailable] = useState(true), [busy, setBusy] = useState(false);
  const offset = useRef(0), controller = useRef(new AbortController());
  useEffect(() => {const current = new AbortController(); controller.current = current; return () => current.abort();}, []);
  async function read(reset = false) {
    setBusy(true); setError('');
    try {
      const value = await planApi.logs(runId, attempt.attempt_id, reset ? 0 : offset.current, controller.current.signal);
      if (controller.current.signal.aborted) return;
      offset.current = value.next_offset; setEof(value.eof); setAvailable(value.available);
      setText(current => ((reset ? '' : current) + value.data).slice(-65536)); setOpen(true);
    } catch (failure) {if (!controller.current.signal.aborted) setError((failure as Error).message);}
    finally {if (!controller.current.signal.aborted) setBusy(false);}
  }
  return <div className="plan-attempt"><div className="plan-section-title"><strong>{attempt.unit_id} · #{attempt.ordinal}</strong><span>{planStatus(attempt.state)}</span><small>{attempt.exit_code == null ? '' : `exit ${attempt.exit_code}`}</small>
    <button className="text-button" disabled={busy} onClick={() => open ? setOpen(false) : void read()}>{open ? t('收起日志') : t('查看日志')}</button></div>
    {attempt.error_code && <small className="plan-error">{attempt.error_code}</small>}
    {error && <p role="alert" className="modal-error">{error}<button className="text-button" onClick={() => void read(true)}>{t('从头读取日志')}</button></p>}
    {open && <><pre className="plan-log">{available ? text || t('暂无日志内容') : t('日志尚未生成')}</pre><button className="text-button" disabled={busy} onClick={() => void read()}>{eof ? t('刷新日志') : t('继续读取日志')}</button></>}
  </div>;
}

function ArtifactFiles({runId, artifact}: {runId: string; artifact: PlanArtifact}) {
  const [page, setPage] = useState<PlanPage<PlanFile, 'files'> | null>(null), [error, setError] = useState('');
  const [preview, setPreview] = useState<{name: string; value: PlanFilePreview} | null>(null), [busy, setBusy] = useState(false);
  const controller = useRef(new AbortController());
  const urls = useRef<string[]>([]);
  useEffect(() => {const current = new AbortController(); controller.current = current; return () => {current.abort(); urls.current.forEach(value => URL.revokeObjectURL(value));};}, []);
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('');
    try {await work();} catch (failure) {if (!controller.current.signal.aborted) setError((failure as Error).message);}
    finally {if (!controller.current.signal.aborted) setBusy(false);}
  }
  return <div className="plan-artifact"><div className="plan-section-title"><strong>{artifact.unit_id}</strong><span>{artifact.size_bytes.toLocaleString()} B</span>{!!artifact.reused && <small>{t('已复用')}</small>}
    <button className="text-button" disabled={busy} onClick={() => void act(async () => setPage(await planApi.files(runId, artifact.artifact_id, '', controller.current.signal)))}>{t('查看文件')}</button></div>
    {error && <p className="modal-error" role="alert">{error}</p>}
    {page?.files.map(file => <div className="plan-file" key={file.file_id}><span title={file.name}>{file.name}</span><small>{file.size_bytes.toLocaleString()} B</small>
      <button className="text-button" disabled={busy} onClick={() => void act(async () => setPreview({name: file.name, value: await planApi.preview(runId, artifact.artifact_id, file.file_id, controller.current.signal)}))}>{t('预览')}</button>
      <button className="text-button" disabled={busy} onClick={() => {
        const host = createDesktopHost();
        if (host.kind === 'tauri') {
          void act(() => openNativeArtifact(host, {run: runId, artifact: artifact.artifact_id, file: file.file_id}, async () => {
            const blob = await planApi.open(runId, artifact.artifact_id, file.file_id, controller.current.signal);
            if (!controller.current.signal.aborted) downloadBlob(file.name.split('/').pop() || file.name, blob);
          }));
          return;
        }
        const inline = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf'].includes(file.media_type);
        const opened = inline ? window.open('about:blank', '_blank') : null;
        if (opened) opened.opener = null;
        void act(async () => {try {
          const blob = await planApi.open(runId, artifact.artifact_id, file.file_id, controller.current.signal);
          if (controller.current.signal.aborted) {opened?.close(); return;}
          if (opened) {const url = URL.createObjectURL(new Blob([blob], {type: file.media_type})); urls.current.push(url); opened.location.replace(url);}
          else downloadBlob(file.name.split('/').pop() || file.name, blob);
        } catch (failure) {opened?.close(); throw failure;}});
      }}>{t(['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'application/pdf'].includes(file.media_type) ? '打开原文件' : '保存原文件')}</button></div>)}
    {page?.has_more && <button className="text-button" disabled={busy} onClick={() => void act(async () => setPage(await planApi.files(runId, artifact.artifact_id, page.next_cursor, controller.current.signal)))}>{t('下一页')}</button>}
    {preview && <div><strong>{preview.name}</strong><pre className="plan-log">{preview.value.kind === 'text' ? preview.value.content : t('二进制文件，请打开原文件查看。')}</pre>
      {preview.value.truncated && <small>{t('仅显示有界预览')}</small>}</div>}
  </div>;
}
export function planStatus(status: string) {
  const labels: Record<string, string> = {queued: '排队中', submitted: '已提交', running: '运行中', complete: '已完成', succeeded: '已完成', failed: '失败', cancelled: '已取消', cancelling: '取消中', admitted: '已接收', blocked: '等待依赖', recovery_required: '需要恢复', building: '正在构建', unknown: '结果待确认'};
  return t(labels[status] || status);
}
