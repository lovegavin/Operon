import {useEffect, useState} from 'react';
import {CircleNotch, Package} from '@phosphor-icons/react';
import {api} from './api';
import {t} from './i18n';
import type {RemoteLibraryCheck, RemoteLibraryOperation} from './types';

const reasons: Record<string, string> = {
  server_upgrade_required: '请先安装 / 升级服务端以补齐算子。',
  remote_package_disabled: '服务端已禁用此包，请在服务端管理。',
  remote_only_entries: '服务端含本地没有的算子，为避免丢失，不能覆盖此包。',
  different_provider: '同名算子属于不同的包，请先解决冲突。',
};
const phases: Record<string, string> = {checking: '核对算子库', packaging: '准备算子包', hashing: '校验算子包',
  uploading: '上传算子包', verifying: '验证上传', resumed: '复用上传', installing: '注册服务端算子'};

export function RemoteLibraryPanel({id, initial, disabled, onBusyChange, onUpdate}: {
  id: string; initial?: RemoteLibraryCheck; disabled: boolean;
  onBusyChange: (busy: boolean) => void; onUpdate: () => Promise<void>;
}) {
  const [check, setCheck] = useState<RemoteLibraryCheck | undefined>(initial);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [operation, setOperation] = useState<RemoteLibraryOperation>({status: 'idle'});
  const running = operation.status === 'running';
  useEffect(() => {onBusyChange(busy || running); return () => onBusyChange(false);}, [busy, running, onBusyChange]);
  useEffect(() => {setCheck(initial); setSelected([]);}, [initial]);
  // Connection already compares manifests. For a pre-existing connection made
  // by CLI/API, fetch once when opening settings, and recover pending transfers.
  useEffect(() => {
    let alive = true;
    if (!initial) void api.checkRemoteLibrary(id).then(value => {if (alive) setCheck(value);}).catch(e => {if (alive) setError(e.message);});
    void api.remoteLibraryStatus(id).then(value => {if (alive && value.status === 'running') setOperation(value);}).catch(() => {});
    return () => {alive = false;};
  }, [id]); // initial is a connection snapshot, not a trigger for repeat requests
  useEffect(() => {
    if (!running) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await api.remoteLibraryStatus(id);
        if (!alive) return;
        setOperation(value);
        if (value.status === 'running') timer = setTimeout(poll, 700);
        else {
          if (value.status === 'failed') setError(value.error || t('补齐失败，请重新检查后重试。'));
          if (value.result) {setCheck(value.result); setSelected([]);}
          await onUpdate();
        }
      } catch (e) {
        if (alive) {setError((e as Error).message); setOperation({status: 'failed'});}
      }
    }
    void poll();
    return () => {alive = false; clearTimeout(timer);};
  // A new onUpdate closure from parent polling must not interrupt an in-flight
  // status request on a slower SSH connection.
  }, [id, running]);
  async function inspect() {
    if (busy || running || disabled) return;
    setBusy(true); setError('');
    try {setCheck(await api.checkRemoteLibrary(id)); setSelected([]); setOperation({status: 'idle'});}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  async function install() {
    if (busy || running || disabled || !selected.length || !check?.local_revision || !check.remote_revision) return;
    setBusy(true); setError('');
    try {setOperation(await api.installRemoteLibrary(id, {packages: selected,
      local_revision: check.local_revision, remote_revision: check.remote_revision}));}
    catch (e) {setError((e as Error).message);}
    finally {setBusy(false);}
  }
  const locked = busy || running || disabled;
  return <section className="remote-library" aria-label={t('服务器算子库')}>
    <div className="remote-status-heading"><strong><Package size={16}/>{t('服务器算子库')}</strong>
      <button type="button" className="subtle-button" disabled={locked} onClick={() => void inspect()}>
        {busy ? t('检查中') : t('检查算子库')}</button></div>
    {check && !check.error && <div role="status">{check.missing_count ? t('服务端缺少 {count} 个本地算子 / Reader', {count: check.missing_count}) : t('服务端没有缺少的本地算子')}
      {check.supported === false && <p>{t(reasons.server_upgrade_required)}</p>}</div>}
    {!!check?.packages?.length && <div className="remote-library-packages">
      {check.packages.map(pkg => <div className="remote-library-package" key={pkg.name}>
        <label><input type="checkbox" disabled={locked || !pkg.selectable} checked={selected.includes(pkg.name)}
          onChange={e => setSelected(previous => e.target.checked ? [...previous, pkg.name] : previous.filter(name => name !== pkg.name))}/>
          <span><strong>{pkg.name}</strong><small>{pkg.remote_version ? `${pkg.remote_version} → ${pkg.version}` : pkg.version}</small></span>
          <span className="remote-library-count">+{pkg.missing.length}</span></label>
        {!!pkg.replaces && <p>{t('整包补齐，将同时更新服务端已有的 {count} 个算子 / Reader。', {count: pkg.replaces})}</p>}
        {pkg.reason && <p className="field-error">{t(reasons[pkg.reason] || pkg.reason)}</p>}
        <details><summary>{t('查看算子')}</summary><ul>{[...pkg.missing, ...pkg.disabled].map(entry =>
          <li key={`${entry.kind}:${entry.id}`}><span>{entry.title || entry.id}</span><code>{entry.id}</code></li>)}</ul></details>
      </div>)}
    </div>}
    {(error || check?.error) && <p className="field-error" role="alert">{error || check?.error}</p>}
    {running && <div className="remote-library-progress" role="status"><CircleNotch size={15} className="spin"/>
      {t(phases[operation.phase || 'checking'] || '正在补齐算子库')}
      {operation.package && <span>{operation.package} ({operation.index}/{operation.total})</span>}
      {!!operation.bytes_total && <progress max={operation.bytes_total} value={operation.bytes_done || 0}/>}</div>}
    {operation.status === 'complete' && <p role="status">{t('算子已补齐；运行依赖请在执行设置中检查。')}</p>}
    {!!check?.packages?.some(pkg => pkg.selectable) && <button type="button" className="primary-button" disabled={locked || !selected.length} onClick={() => void install()}>
      {t('补齐所选算子包')}{selected.length ? ` (${selected.length})` : ''}</button>}
  </section>;
}
