import { useEffect, useRef, useState } from 'react';
import { Modal } from './RouteDialogs';
import { t } from './i18n';
import { api } from './api';
import type { EnvironmentSnapshot, PoolStatus, RemoteEnvironments } from './api';

function size(bytes: number) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes, index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

const statusLabel: Record<string, string> = {
  missing: '未安装', stale: '需要更新', ready: '已就绪', failed: '准备失败',
  running: '安装中', complete: '已完成', queued: '排队中', preparing: '准备中',
  recovery_required: '需要恢复',
};

export function RuntimeStatusPanel({ onClose }: { onClose: () => void }) {
  const [pool, setPool] = useState<PoolStatus | null>(null);
  const [environments, setEnvironments] = useState<EnvironmentSnapshot | null>(null);
  const [error, setError] = useState('');
  const [remoteEnvironments, setRemoteEnvironments] = useState<Record<string, RemoteEnvironments>>({});
  const [remoteEnvironmentBusy, setRemoteEnvironmentBusy] = useState<Record<string, boolean>>({});
  const [remoteEnvironmentError, setRemoteEnvironmentError] = useState<Record<string, string>>({});
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const refresh = () => {
      Promise.all([api.pool(), api.environments()])
        .then(([nextPool, nextEnvironments]) => {
          if (!mounted.current) return;
          setPool(nextPool); setEnvironments(nextEnvironments); setError('');
        })
        .catch((e: Error) => {if (mounted.current) setError(e.message);});
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => {mounted.current = false; clearInterval(timer);};
  }, []);
  const loadRemoteEnvironments = async (id: string) => {
    setRemoteEnvironmentBusy(current => ({...current, [id]: true}));
    try {
      const next = await api.remoteEnvironments(id);
      setRemoteEnvironments(current => ({...current, [id]: next}));
      setRemoteEnvironmentError(current => ({...current, [id]: ''}));
    } catch (failure) {
      setRemoteEnvironmentError(current => ({...current, [id]: (failure as Error).message}));
    } finally {
      setRemoteEnvironmentBusy(current => ({...current, [id]: false}));
    }
  };
  const prepareRemoteEnvironments = async (id: string) => {
    setRemoteEnvironmentBusy(current => ({...current, [id]: true}));
    try {
      await api.remotePrepareEnvironments(id);
      setRemoteEnvironmentError(current => ({...current, [id]: ''}));
    } catch (failure) {
      setRemoteEnvironmentError(current => ({...current, [id]: (failure as Error).message}));
    } finally {
      setRemoteEnvironmentBusy(current => ({...current, [id]: false}));
      await loadRemoteEnvironments(id);
    }
  };
  useEffect(() => {
    (pool?.remotes || []).filter(remote => remote.connected && !remoteEnvironments[remote.profile.id])
      .forEach(remote => {void loadRemoteEnvironments(remote.profile.id);});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pool]);

  const instance = pool?.instance;
  const jobs = environments?.operations || [];
  const running = jobs.filter(job => job.status === 'running');
  return <Modal title={t('运行状态')} onClose={onClose}>
    {error && <pre className="modal-error">{error}</pre>}
    <section className="runtime-section">
      <h4>{t('本地共享池')}</h4>
      {!instance?.version ? <p className="modal-empty">{t('尚未启动共享池')}</p> : <>
        <p>{t('版本')} <span className="mono">{instance.version}</span> · PID <span className="mono">{instance.pid || '—'}</span>
          {instance.closing && <> · {t('正在退出')}</>}</p>
        <p className="muted">{t('已注册工作区')} {pool?.workspaces.length || 0} · {t('运行中任务')} {pool?.active.length || 0}</p>
      </>}
      {!!pool?.active.length && <ul className="runtime-list">{pool.active.map(item =>
        <li key={`${item.workspace}:${item.id}`}><strong>{item.title || item.id}</strong>
          <span>{statusLabel[item.status || ''] || item.status} · {item.workspace}</span></li>)}</ul>}
    </section>
    <section className="runtime-section">
      <h4>{t('隔离环境安装进度')}</h4>
      {!environments?.manifest.present && <p className="modal-empty">{t('当前算子库没有环境清单')}</p>}
      {Object.values(environments?.environments || {}).map(item => {
        const job = running.find(value => value.name === item.name);
        const phase = job?.phase || item.progress?.phase;
        return <article className="runtime-environment" key={item.name}>
          <div><strong>{item.name}</strong> <span>{statusLabel[item.status] || item.status}</span></div>
          <p>{t('Python')} {item.python} · {item.used_by.length} {t('个算子')}
            {phase && <> · {phase}</>}
            {!!job?.bytes && <> · {size(job.bytes)} / {job.files} {t('个文件')}</>}</p>
          {item.error && <pre className="modal-error">{item.error}</pre>}
        </article>;
      })}
    </section>
    <section className="runtime-section">
      <h4>{t('服务器连接')}</h4>
      {!pool?.remotes.length && <p className="modal-empty">{t('没有配置服务器')}</p>}
      {pool?.remotes.map(remote => <article className="runtime-environment" key={remote.profile.id}>
        <div><strong>{remote.profile.name || remote.profile.host}</strong>
          <span>{remote.connected ? t('已连接') : t('未连接')}</span></div>
        <p>{remote.info?.build?.application?.version || '—'}{remote.info?.library_check?.replacement_required ? ` · ${t('算子库需要更新')}` : ''}</p>
        {remote.connected && <div className="runtime-remote-pool">
          <h5>{t('远程共享池')}</h5>
          {remote.pool?.available ? <>
            <p><span className="mono">{remote.pool.version || '—'}</span> · PID{' '}
              <span className="mono">{remote.pool.owner?.pid || '—'}</span>
              {remote.pool.closing && <> · {t('正在退出')}</>}</p>
            <p className="muted">{t('运行中任务')} {remote.pool.active_count || 0}
              {' · '}{t('会话')} {remote.pool.sessions ?? 0}</p>
            {!!remote.pool.active_jobs?.length && <ul className="runtime-list">{remote.pool.active_jobs.map(job =>
              <li key={job.id}><strong>{job.title || job.id}</strong>
                <span>{statusLabel[job.status || ''] || job.status}</span></li>)}</ul>}
          </> : <p className="muted">{remote.pool?.unsupported ? t('服务端版本较旧，无法读取池状态')
            : (remote.pool?.error || t('尚未启动共享池'))}</p>}
        </div>}
        {remote.connected && <div className="runtime-remote-pool">
          <h5>{t('远程环境')}
            <button className="subtle-button" onClick={() => void loadRemoteEnvironments(remote.profile.id)}>
              {t('读取')}
            </button>
          </h5>
          {remoteEnvironmentBusy[remote.profile.id] && <p className="muted">{t('读取中…')}</p>}
          {remoteEnvironmentError[remote.profile.id] &&
            <p className="muted">{remoteEnvironmentError[remote.profile.id]}</p>}
          {remoteEnvironments[remote.profile.id]?.error &&
            <p className="muted">{remoteEnvironments[remote.profile.id].error}</p>}
          {!!Object.keys(remoteEnvironments[remote.profile.id]?.environments || {}).length && <>
            <ul className="runtime-list">
              {Object.entries(remoteEnvironments[remote.profile.id]?.environments || {}).map(([name, item]) =>
                <li key={name}><strong>{name}</strong>
                  <span>{statusLabel[item.status || ''] || item.status}
                    {item.progress?.phase ? ` · ${item.progress.phase}` : ''}
                    {item.progress?.detail ? ` · ${item.progress.detail}` : ''}</span></li>)}
            </ul>
            <button className="primary-button" onClick={() => void prepareRemoteEnvironments(remote.profile.id)}>
              {t('准备远程环境')}
            </button>
          </>}
        </div>}
      </article>)}
    </section>
  </Modal>;
}
