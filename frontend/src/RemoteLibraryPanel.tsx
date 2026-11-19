import {useEffect, useRef, useState} from 'react';
import {CircleNotch, Package} from '@phosphor-icons/react';
import {api} from './api';
import {t} from './i18n';
import type {RemoteLibraryCheck, RemoteLibraryOperation, RemoteLibraryPlan} from './types';

const reasons: Record<string, string> = {
  server_upgrade_required: '请先安装 / 升级服务端以补齐算子。',
  remote_package_disabled: '服务端已禁用此包，请在服务端管理。',
  remote_only_entries: '服务端含本地没有的算子，为避免丢失，不能覆盖此包。',
  different_provider: '同名算子属于不同的包，请先解决冲突。',
  implementation_changed: '服务端算子实现与本地不一致，需要整体替换。',
};

const phases: Record<string, string> = {
  checking: '正在比较两个算子库…',
  packaging: '正在打包本地算子包…',
  installing: '正在上传并安装到服务器…',
  removing: '正在删除服务器上多余的算子包…',
  refreshing: '正在刷新服务端算子目录…',
  complete: '同步完成。',
};

export function RemoteLibraryPanel({id, initial, disabled, onBusyChange, onUpdate, onInstall}: {
  id: string; initial?: RemoteLibraryCheck; disabled: boolean;
  onBusyChange: (busy: boolean) => void; onUpdate: () => Promise<void>; onInstall: () => void;
}) {
  const [check, setCheck] = useState<RemoteLibraryCheck | undefined>(initial);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [plan, setPlan] = useState<RemoteLibraryPlan | undefined>(undefined);
  const [running, setRunning] = useState<RemoteLibraryOperation | undefined>(undefined);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => {setCheck(initial); setError('');}, [initial]);
  useEffect(() => {onBusyChange(busy); return () => onBusyChange(false);}, [busy, onBusyChange]);
  useEffect(() => {
    let alive = true;
    if (!initial) void api.checkRemoteLibrary(id).then(value => {if (alive) setCheck(value);}).catch(e => {if (alive) setError(e.message);});
    return () => {alive = false;};
  }, [id]);
  useEffect(() => () => {if (timer.current) window.clearTimeout(timer.current);}, []);
  async function inspect() {
    if (busy || disabled) return;
    setBusy(true); setError(''); setPlan(undefined);
    try {setCheck(await api.checkRemoteLibrary(id)); await onUpdate();}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  async function inspectPlan() {
    if (busy || disabled) return;
    setBusy(true); setError(''); setRunning(undefined);
    try {setPlan(await api.remoteLibraryPlan(id));}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  function poll() {
    timer.current = window.setTimeout(async () => {
      try {
        const state = await api.remoteLibraryStatus(id);
        setRunning(state);
        if (state.status === 'running') {poll(); return;}
        setBusy(false); setPlan(undefined);
        if (state.status === 'complete') {setCheck(await api.checkRemoteLibrary(id)); await onUpdate();}
        else if (state.status === 'failed') setError(state.error || t('同步失败。'));
      } catch (e) {
        setBusy(false); setError((e as Error).message);
      }
    }, 900);
  }
  async function sync() {
    if (busy || disabled) return;
    setBusy(true); setError('');
    try {setRunning(await api.syncRemoteLibrary(id)); poll();}
    catch (e) {setBusy(false); setError((e as Error).message);}
  }
  const adding = plan?.install?.length || 0, removing = plan?.remove?.length || 0;
  return <section className="remote-library" aria-label={t('服务器算子库')}>
    <div className="remote-status-heading"><strong><Package size={16}/>{t('服务器算子库')}</strong>
      <button type="button" className="subtle-button" disabled={busy || disabled} onClick={() => void inspect()}>
        {busy ? <><CircleNotch size={14} className="spin"/>{t('检查中')}</> : t('检查算子库')}</button></div>
    {check && !check.error && <div role="status">
      {check.missing_count ? t('服务端缺少 {count} 个本地算子 / Reader', {count: check.missing_count}) : t('服务端没有缺少的本地算子')}
      {!!check.changed_count && <p>{t('服务端有 {count} 个算子实现与本地不一致，需要整体替换。', {count: check.changed_count})}</p>}
      {check.supported === false && <p>{t(reasons.server_upgrade_required)}</p>}
      {check.supported !== false && check.replacement_required && <p>{t('服务端构建与本地不一致，请安装 / 升级服务端以整体替换算子库。')}</p>}
    </div>}
    {!!check?.packages?.length && <details className="remote-library-packages">
      <summary>{t('查看服务端算子包')}</summary>
      <ul>{check.packages.map(pkg => <li key={pkg.name}>
        <strong>{pkg.name}</strong>
        <small>{pkg.remote_version ? `${pkg.remote_version} → ${pkg.version}` : pkg.version}</small>
        {!!pkg.replaces && <span>{t('将同时更新服务端已有的 {count} 个算子 / Reader。', {count: pkg.replaces})}</span>}
        {pkg.reason && <span className="field-error">{t(reasons[pkg.reason] || pkg.reason)}</span>}
      </li>)}</ul>
    </details>}
    {plan && <div className="remote-library-plan" role="status">
      <p>{t('强制同步会以本机为准，把服务器算子库改成与本机完全一致。')}</p>
      <ul>
        <li>{t('将添加 {count} 个算子包。', {count: adding})}{adding ? ` ${plan.install.join('、')}` : ''}</li>
        <li>{t('将删除 {count} 个本机没有的算子包。', {count: removing})}{removing ? ` ${plan.remove.join('、')}` : ''}</li>
      </ul>
      {!!plan.blocked?.length && <p className="field-error">
        {t('以下包会被跳过：')}{plan.blocked.map(item => `${item.name}（${t(reasons[item.reason || ''] || item.reason || '')}）`).join('、')}
      </p>}
      {plan.removal_supported === false && <p className="field-error">{t('服务端还不支持删除多余的算子包，本次只补齐缺少的包。')}</p>}
      <div className="remote-library-actions">
        <button type="button" className="primary-button" disabled={busy} onClick={() => void sync()}>
          {busy ? <><CircleNotch size={14} className="spin"/>{t('同步中')}</> : t('开始强制同步')}</button>
        <button type="button" className="subtle-button" disabled={busy} onClick={() => setPlan(undefined)}>{t('取消')}</button>
      </div>
    </div>}
    {running && <p role="status">{(phases[running.phase || ''] || t('正在同步算子库'))}
      {running.status === 'running' && !!running.total && running.index ? ` (${running.index}/${running.total})` : ''}</p>}
    {running?.status === 'complete' && !plan && <p role="status">{t('同步完成：已删除 {removed} 个包，已补齐 {added} 个包。',
      {removed: (running.removed || []).length, added: (running.installed || []).length})}</p>}
    {(error || check?.error) && <p className="field-error" role="alert">{error || check?.error}</p>}
    <p className="remote-library-note">{t('服务端算子库需要更新时，请使用“安装 / 升级服务端”整体替换，或点击“强制同步算子库”以本机为准增删算子包。')}</p>
    <div className="remote-library-actions">
      <button type="button" className="subtle-button" disabled={busy || disabled} onClick={() => void inspectPlan()}>
        {t('强制同步算子库')}</button>
      <button type="button" className="primary-button" disabled={busy || disabled} onClick={onInstall}>
        {t('安装 / 升级服务端')}</button>
    </div>
  </section>;
}
