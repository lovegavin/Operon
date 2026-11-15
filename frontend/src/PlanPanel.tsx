import {useEffect, useRef, useState} from 'react';
import {ArrowClockwise, FileArrowUp, Play, DownloadSimple} from '@phosphor-icons/react';
import {Modal} from './RouteDialogs';
import {ApiError, downloadText} from './api';
import {t} from './i18n';
import {planApi} from './planApi';
import {appendRecord, bindingProblems, emptyBinding, parsePlanFile, recordSubmission, requiredBindings} from './planState';
import {PlanRunResults} from './PlanRunResults';
import {PlanExportPanel} from './PlanExportPanel';
import type {Graph} from './types';
import type {BindingOptions, PlanBinding, PlanCompile, PlanRecord, PlanUiState, RunPlan} from './planTypes';
import './planPanel.css';

type Props = {graph: Graph; onClose: () => void};
export function PlanPanel({graph, onClose}: Props) {
  const [store, setStore] = useState<PlanUiState | null>(null);
  const [plan, setPlan] = useState<RunPlan | null>(null);
  const [binding, setBinding] = useState<PlanBinding>(emptyBinding);
  const [options, setOptions] = useState<BindingOptions | null>(null);
  const [source, setSource] = useState<{title: string; compile: PlanCompile} | null>(null);
  const [selected, setSelected] = useState('');
  const [tab, setTab] = useState<'prepare' | 'runs' | 'export'>('prepare');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const state = useRef<PlanUiState | null>(null), controller = useRef(new AbortController());
  const fileInput = useRef<HTMLInputElement>(null), bindingInput = useRef<HTMLInputElement>(null);
  const selectedRecord = store?.records.find(item => item.submission.request_id === selected);
  const shownPlan = selectedRecord?.submission.plan || plan;
  const shownBinding = selectedRecord?.submission.binding || binding;
  const locked = !!selectedRecord;
  const missing = shownPlan ? bindingProblems(shownPlan, shownBinding) : [];
  const required = shownPlan ? requiredBindings(shownPlan) : {environments: [], storage: [], inputs: []};
  useEffect(() => {
    const current = new AbortController(); controller.current = current;
    planApi.state(current.signal).then(value => {state.current = value; setStore(value);})
      .catch(failure => {if (!current.signal.aborted) setError((failure as Error).message);});
    return () => current.abort();
  }, []);
  const save = async (next: PlanUiState) => {
    const value = await planApi.saveState(next, controller.current.signal);
    state.current = value; if (!controller.current.signal.aborted) setStore(value); return value;
  };
  async function action(name: string, work: () => Promise<void>) {
    if (busy) return;
    setBusy(name); setError('');
    try {await work();} catch (failure) {
      if (!controller.current.signal.aborted) setError((failure as Error).message);
    } finally {if (!controller.current.signal.aborted) setBusy('');}
  }
  async function compile() {
    const snapshot = source?.compile || {kind: 'graph' as const, workflow: structuredClone(graph) as unknown as Record<string, unknown>};
    await action('compile', async () => {
      const next = await planApi.compile(structuredClone(snapshot), controller.current.signal);
      setPlan(next); setBinding(emptyBinding()); setOptions(null); setSelected('');
    });
  }
  async function importFile(file?: File) {
    if (!file) return;
    await action('import', async () => {
      const imported = parsePlanFile(await file.text());
      setSelected(''); setOptions(null);
      if (imported.plan) {setPlan(imported.plan); setBinding(imported.binding || emptyBinding()); setSource(null);}
      else {setPlan(null); setSource({title: file.name, compile: imported.compile!});}
    });
  }
  async function inspectBindings() {
    if (!plan || locked) return;
    await action('bindings', async () => {
      const paths = Object.fromEntries(required.inputs.filter(name => binding.inputs[name]?.path).map(name =>
        [name, {path: binding.inputs[name].path, representation: binding.inputs[name].representation}]));
      const next = await planApi.bindingOptions(plan, binding, controller.current.signal, paths);
      setOptions(next);
      setBinding(current => ({...current, package_root: next.package_root, environment_store: next.environment_store,
        environments: Object.fromEntries(required.environments.flatMap(name => {
          const items = (next.environments[name] || []).filter(item => item.verified);
          const old = current.environments[name];
          const chosen = items.find(item => item.generation_id === old?.generation_id && item.executable === old?.executable) || (items.length === 1 ? items[0] : undefined);
          return chosen ? [[name, {generation_id: chosen.generation_id, executable: chosen.executable}]] : [];
        })), storage: {...current.storage, ...next.storage}, inputs: {...current.inputs, ...next.inputs}}));
    });
  }
  async function submit(record?: PlanRecord) {
    if (!state.current || (!plan && !record)) return;
    await action('submit', async () => {
      const entry = record || recordSubmission(plan!, binding, source?.title || graph.name);
      // Persist the exact body before any network submission. Reopening a pending
      // receipt can only repeat this body and request ID, never new canvas values.
      if (!record) await save(appendRecord(state.current!, entry));
      setSelected(entry.submission.request_id); setTab('runs');
      try {
        const result = await planApi.submit(entry.submission, controller.current.signal);
        await save({...state.current!, records: state.current!.records.map(item => item.submission.request_id === entry.submission.request_id
          ? {...item, run_id: result.run_id, status: 'accepted'} : item)});
      } catch (failure) {
        const uncertain = !(failure instanceof ApiError) || !failure.status || failure.status >= 500 || failure.code === 'submission_unknown';
        if (!controller.current.signal.aborted) await save({...state.current!, records: state.current!.records.map(item => item.submission.request_id === entry.submission.request_id
          ? {...item, status: uncertain ? 'unknown' : 'rejected'} : item)});
        throw failure;
      }
    });
  }
  const updateInput = (name: string, path: string) => setBinding(current => ({...current, inputs: {...current.inputs,
    [name]: {representation: current.inputs[name]?.representation || 'file', path, sha256: '', size_bytes: 0, metadata: {}}}}));

  return <Modal title={t('执行计划')} subtitle={t('编译快照 · 固定环境 · 显式运行')} onClose={onClose}>
    <div className="plan-panel">
      <nav className="plan-tabs" aria-label={t('执行计划栏目')}>
        {(['prepare', 'runs', 'export'] as const).map(key => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>
          {t(key === 'prepare' ? '准备计划' : key === 'runs' ? '计划记录' : '独立导出')}
          {key === 'runs' && !!store?.records.length && <span className="count-badge">{store.records.length}</span>}
        </button>)}
      </nav>
      {error && <div role="alert" className="modal-error plan-error">{error}
        <button className="text-button" disabled={!!busy} onClick={() => void action('reload', async () => {const latest = await planApi.state(controller.current.signal); state.current = latest; setStore(latest);})}>{t('重新读取记录')}</button></div>}
      {tab === 'prepare' && <>
        <div className="plan-source"><div><span className="eyebrow">{t('来源')}</span><h3>{source?.title || graph.name}</h3>
          <p>{t('编译仅冻结当前代码、参数和资源要求，不启动任务或安装依赖。')}</p></div>
          <button className="subtle-button" disabled={!!busy} onClick={() => fileInput.current?.click()}><FileArrowUp size={16}/>{t('导入计划或清单')}</button>
          <button className="primary-button" disabled={!!busy} onClick={() => void compile()}>{t('编译快照')}</button>
        </div>
        {source && <button className="text-button" disabled={!!busy} onClick={() => {setSource(null); setSelected(''); setPlan(null);}}>{t('使用当前画布')}</button>}
        {shownPlan && <>
          <PlanSummary plan={shownPlan}/>
          {locked && <p className="plan-note">{t('这是已提交的固定快照。重新编译会创建另一份计划，不会修改原任务。')}</p>}
          <section className="plan-bindings"><div className="plan-section-title"><h3>{t('执行绑定')}</h3>
            <button className="subtle-button" disabled={!!busy || locked} onClick={() => void inspectBindings()}><ArrowClockwise size={15}/>{t('核对环境与输入')}</button>
            <button className="text-button" disabled={!!busy || locked} onClick={() => bindingInput.current?.click()}>{t('导入绑定清单')}</button></div>
            <p className="plan-note">{t('所有路径相对于当前服务的工作区。只读取已准备的环境，不自动安装。')}</p>
            <div className="plan-fields">{(['package_root', 'environment_store'] as const).map(key => <label className="field" key={key}><span>{t(key === 'package_root' ? '程序目录' : '环境仓库')}</span>
              <input value={shownBinding[key]} disabled={locked || !!busy} onChange={event => {setOptions(null); setBinding(current => ({...current, [key]: event.target.value, environments: {}}));}}/></label>)}</div>
            {required.environments.map(name => <div className="plan-binding-row" key={name}><strong>{name || t('未声明环境')}</strong>
              {options && !locked ? <label className="field"><span>{t('已验证的环境版本')}</span><select aria-label={`${t('环境')} ${name}`} disabled={!!busy} value={shownBinding.environments[name]?.generation_id || ''} onChange={event => {
                const item = options.environments[name]?.find(value => value.generation_id === event.target.value && value.verified);
                setBinding(current => ({...current, environments: {...current.environments, [name]: item ? {generation_id: item.generation_id, executable: item.executable} : {generation_id: '', executable: ''}}}));
              }}><option value="">{t('请选择已验证环境')}</option>{(options.environments[name] || []).filter(item => item.verified).map(item => <option key={item.generation_id} value={item.generation_id}>{item.label || item.generation_id}</option>)}</select></label>
                : <p className="mono">{shownBinding.environments[name]?.generation_id || t('尚未绑定环境')}</p>}
              {shownBinding.environments[name]?.executable && <small className="mono">{shownBinding.environments[name].executable}</small>}
            </div>)}
            {required.storage.map(name => <label className="field" key={name}><span>{t('存储')} · {name}</span><input disabled={locked || !!busy} value={shownBinding.storage[name] || ''} placeholder="data" onChange={event => setBinding(current => ({...current, storage: {...current.storage, [name]: event.target.value}}))}/></label>)}
            {required.inputs.map(name => <div className="plan-binding-row" key={name}><strong>{t('输入')} · {name}</strong><label className="field"><span>{t('文件相对路径')}</span><input disabled={locked || !!busy} value={shownBinding.inputs[name]?.path || ''} onChange={event => updateInput(name, event.target.value)}/></label>
              <label className="field"><span>{t('表示格式')}</span><select disabled={locked || !!busy} value={shownBinding.inputs[name]?.representation || 'file'} onChange={event => setBinding(current => ({...current, inputs: {...current.inputs, [name]: {...(current.inputs[name] || {path: '', size_bytes: 0, metadata: {}}), representation: event.target.value as 'file', sha256: ''}}}))}>
                {['file', 'form', 'table', 'json', 'npy', 'report', 'figure'].map(value => <option key={value}>{value}</option>)}</select></label>
              {shownBinding.inputs[name]?.sha256 && <small className="mono">{shownBinding.inputs[name].size_bytes} B · SHA256 {shownBinding.inputs[name].sha256.slice(0, 16)}…</small>}
            </div>)}
            {!!missing.length && <ul className="plan-missing">{missing.map(value => <li key={value}>{value}</li>)}</ul>}
            {options?.missing?.map(value => <p className="plan-note" key={value}>{value}</p>)}
          </section>
          <div className="plan-actions"><button className="subtle-button" onClick={() => downloadText('execution-plan.json', JSON.stringify({plan: shownPlan, binding: shownBinding}, null, 2), 'application/json')}><DownloadSimple size={15}/>{t('保存计划清单')}</button>
            <button className="primary-button" disabled={!store || !!busy || locked || !!missing.length} onClick={() => void submit()}><Play size={15}/>{t('提交此计划')}</button></div>
        </>}
      </>}
      {tab === 'runs' && <>
        {!store?.records.length && <p className="modal-empty">{t('暂无执行计划记录')}</p>}
        <div className="plan-history">{store?.records.map(item => <button key={item.submission.request_id} aria-pressed={selected === item.submission.request_id} onClick={() => setSelected(item.submission.request_id)}><strong>{item.title}</strong><span>{item.run_id || t('等待确认提交')}</span><small>{new Date(item.created_at).toLocaleString()}</small></button>)}</div>
        {selectedRecord && <><PlanSummary plan={selectedRecord.submission.plan}/><p className="plan-request mono">{t('提交标识')} · {selectedRecord.submission.request_id}</p>
          {['accepted', 'rejected'].includes(selectedRecord.status) && <button className="text-button" disabled={!!busy} onClick={() => void action('archive', async () => {
            await save({...state.current!, records: state.current!.records.filter(item => item.submission.request_id !== selected)}); setSelected('');
          })}>{t('从此列表归档')}</button>}
          {!selectedRecord.run_id && <div role="status" className="plan-note"><p>{t(selectedRecord.status === 'rejected' ? '服务拒绝了这次提交。原请求保留，重试仍使用同一标识。' : '尚未确认服务是否接收。重试将使用原始请求标识与固定快照，不会创建新的提交身份。')}</p>
            <button className="primary-button" disabled={!!busy} onClick={() => void submit(selectedRecord)}>{t('用原标识确认提交')}</button></div>}
          {selectedRecord.run_id && <PlanRunResults key={selectedRecord.run_id} runId={selectedRecord.run_id}/>}
        </>}
      </>}
      {tab === 'export' && <PlanExportPanel plan={shownPlan} binding={shownBinding} store={store} save={save}/>}
      <input ref={fileInput} type="file" accept=".json,application/json" className="sr-only" aria-label={t('导入计划或清单')} onChange={event => {void importFile(event.target.files?.[0]); event.target.value = '';}}/>
      <input ref={bindingInput} type="file" accept=".json,application/json" className="sr-only" aria-label={t('导入绑定清单')} onChange={event => {const file = event.target.files?.[0]; event.target.value = ''; if (file) void action('binding-import', async () => {
        const value = JSON.parse(await file.text()); const next = value.binding || value;
        if (!next.environments || !next.inputs || !next.storage) throw Error(t('执行绑定清单不完整。'));
        setBinding(next); setOptions(null);
      });}}/>
    </div>
  </Modal>;
}

export function PlanSummary({plan}: {plan: RunPlan}) {
  const experimental = plan.units.some(unit => unit.placement.executor === 'slurm' || unit.placement.executor === 'ssh');
  return <section className="plan-summary"><div className="plan-section-title"><h3>{t('固定计划')}</h3><span className="mono" title={plan.plan_id}>{plan.plan_id.slice(0, 16)}</span>{experimental && <span className="plan-experimental">{t('多主机 / Slurm · 实验性')}</span>}</div>
    <dl><div><dt>{t('执行单元')}</dt><dd>{plan.units.length}</dd></div><div><dt>{t('代码实现')}</dt><dd>{Object.keys(plan.implementations || {}).length}</dd></div><div><dt>{t('参数指纹')}</dt><dd className="mono" title={plan.parameters_digest}>{plan.parameters_digest.slice(0, 12)}</dd></div></dl>
    <details><summary>{t('查看执行单元')}</summary><div className="plan-unit-list">{plan.units.map(unit => <div key={unit.unit_id}><strong>{unit.unit_id}</strong><span>{unit.invocation.kind} · {unit.placement.executor} · {unit.placement.target.os}/{unit.placement.target.arch}</span><small>{unit.resource_request.cpu_threads} CPU · {Math.ceil(unit.resource_request.process_reservation_bytes / 1024 / 1024)} MiB</small></div>)}</div></details>
  </section>;
}
