import {useEffect, useState} from 'react';
import {CircleNotch, Package} from '@phosphor-icons/react';
import {api} from './api';
import {t} from './i18n';
import type {RemoteLibraryCheck} from './types';

const reasons: Record<string, string> = {
  server_upgrade_required: '请先安装 / 升级服务端以补齐算子。',
  remote_package_disabled: '服务端已禁用此包，请在服务端管理。',
  remote_only_entries: '服务端含本地没有的算子，为避免丢失，不能覆盖此包。',
  different_provider: '同名算子属于不同的包，请先解决冲突。',
  implementation_changed: '服务端算子实现与本地不一致，需要整体替换。',
};

export function RemoteLibraryPanel({id, initial, disabled, onBusyChange, onUpdate, onInstall}: {
  id: string; initial?: RemoteLibraryCheck; disabled: boolean;
  onBusyChange: (busy: boolean) => void; onUpdate: () => Promise<void>; onInstall: () => void;
}) {
  const [check, setCheck] = useState<RemoteLibraryCheck | undefined>(initial);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => {setCheck(initial); setError('');}, [initial]);
  useEffect(() => {onBusyChange(busy); return () => onBusyChange(false);}, [busy, onBusyChange]);
  // The handshake normally carries the comparison. Fetch once for connections
  // opened by CLI/API, but never upload operator packages from this panel.
  useEffect(() => {
    let alive = true;
    if (!initial) void api.checkRemoteLibrary(id).then(value => {if (alive) setCheck(value);}).catch(e => {if (alive) setError(e.message);});
    return () => {alive = false;};
  }, [id]); // initial is a connection snapshot, not a trigger for repeat requests
  async function inspect() {
    if (busy || disabled) return;
    setBusy(true); setError('');
    try {setCheck(await api.checkRemoteLibrary(id)); await onUpdate();}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
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
    {(error || check?.error) && <p className="field-error" role="alert">{error || check?.error}</p>}
    <p className="remote-library-note">{t('服务端算子库需要更新时，请使用“安装 / 升级服务端”整体替换，不再增量上传算子包。')}</p>
    <button type="button" className="primary-button" disabled={busy || disabled} onClick={onInstall}>
      {t('安装 / 升级服务端')}</button>
  </section>;
}
