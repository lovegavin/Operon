import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowRight, ArrowClockwise, CircleNotch, File, Folder, X} from '@phosphor-icons/react';
import {api, ApiError} from './api';
import {t} from './i18n';
import type {StorageEntry, StoragePage, StoragePreview, StorageRef} from './storageTypes';
import './remote.css';

export function storageParent(path: string): string {
  const parts = path.split('/').filter(part => part && part !== '.');
  return parts.slice(0, -1).join('/') || '.';
}

/** Metadata and bounded previews only. Selection returns the authorized ref. */
export function StorageFilePicker({onClose, onSelect}: {
  onClose: () => void; onSelect?: (reference: StorageRef) => void;
}) {
  const [roots, setRoots] = useState<StorageRef[]>([]);
  const [storage, setStorage] = useState(''), [path, setPath] = useState('.');
  const [location, setLocation] = useState('.'), [hidden, setHidden] = useState(false);
  const [page, setPage] = useState<StoragePage | null>(null);
  const [selected, setSelected] = useState<StorageEntry | null>(null);
  const [preview, setPreview] = useState<StoragePreview | null>(null);
  const [busy, setBusy] = useState(true), [error, setError] = useState('');
  const request = useRef(0), controller = useRef<AbortController | null>(null);
  const session = useRef('');

  function startRequest() {
    controller.current?.abort();
    controller.current = new AbortController();
    return {id: ++request.current, signal: controller.current.signal};
  }

  async function browse(storageId: string, directory: string, showHidden: boolean, cursor?: string) {
    const {id, signal} = startRequest();
    if (!cursor) {
      const previous = session.current;
      session.current = crypto.randomUUID();
      if (previous) void api.closeStorageBrowse(previous).catch(() => {});
      setPage(null);
    }
    const activeSession = session.current;
    setStorage(storageId); setLocation(directory); setPath(directory);
    setSelected(null); setPreview(null); setBusy(true); setError('');
    try {
      const result = await api.browseStorage({storage_id: storageId, relative_path: directory,
        hidden: showHidden, order: 'filesystem', cursor: cursor || null}, activeSession, signal);
      if (id !== request.current) {
        void api.closeStorageBrowse(activeSession).catch(() => {});
        return;
      }
      // Replace pages instead of retaining every entry in a large directory.
      setPage(result);
    } catch (issue) {
      if (id !== request.current) return;
      const code = issue instanceof ApiError ? issue.code : '';
      setError(['browse_cursor_expired', 'browse_cursor_scope', 'browse_changed'].includes(code || '')
        ? t('目录已变化或浏览已过期，请重新加载。') : (issue as Error).message);
      setPage(previous => previous ? {...previous, next_cursor: null} : null);
      void api.closeStorageBrowse(activeSession).catch(() => {});
    } finally {if (id === request.current) setBusy(false);}
  }

  useEffect(() => {
    const {id, signal} = startRequest();
    void api.storageRoots(signal).then(result => {
      if (id !== request.current) return;
      setRoots(result.roots);
      if (result.roots.length) void browse(result.roots[0].storage_id, '.', false);
      else setBusy(false);
    }).catch(issue => {if (id === request.current) {setError((issue as Error).message); setBusy(false);}});
    return () => {
      request.current++;
      controller.current?.abort();
      if (session.current) void api.closeStorageBrowse(session.current).catch(() => {});
    };
  }, []);

  useEffect(() => {
    const escape = (event: KeyboardEvent) => {if (event.key === 'Escape') onClose();};
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [onClose]);

  async function inspect(entry: StorageEntry, choose = false) {
    const {id, signal} = startRequest();
    setBusy(true); setError(''); setPreview(null);
    try {
      const checked = await api.statStorage(entry.ref, session.current, signal);
      if (id !== request.current) return;
      if (!checked.accessible || checked.kind !== 'file') throw new Error(t('此项目不可作为文件读取。'));
      if (choose && onSelect) {onSelect(checked.ref); onClose(); return;}
      const result = await api.previewStorage(checked.ref, session.current, signal);
      if (id !== request.current) return;
      if (result.entry.ref.version !== checked.ref.version) throw new Error(t('文件已变化，请刷新后重试。'));
      setPreview(result);
    } catch (issue) {if (id === request.current) setError((issue as Error).message);}
    finally {if (id === request.current) setBusy(false);}
  }

  return <div className="agent-overlay"><section className="remote-files storage-files" role="dialog" aria-modal="true" aria-label={t('浏览已配置文件')}>
    <header><h2><Folder size={22}/>{t('已配置文件')}</h2><button className="icon-button" aria-label={t('关闭文件选择')} onClick={onClose}><X size={18}/></button></header>
    {!!roots.length && <>
      <label className="storage-root"><span>{t('文件位置')}</span><select aria-label={t('文件位置')} value={storage} disabled={busy}
        onChange={event => void browse(event.target.value, '.', hidden)}>
        {roots.map(root => <option key={root.storage_id} value={root.storage_id}>{root.storage_id}</option>)}
      </select></label>
      <form className="remote-location" onSubmit={event => {event.preventDefault(); void browse(storage, path, hidden);}}>
        <button type="button" className="icon-button" aria-label={t('上级目录')} disabled={busy || location === '.'}
          onClick={() => void browse(storage, storageParent(location), hidden)}><ArrowLeft size={17}/></button>
        <input aria-label={t('相对目录')} value={path} disabled={busy} onChange={event => setPath(event.target.value)}/>
        <button className="icon-button" aria-label={t('打开目录')} disabled={busy}><ArrowRight size={17}/></button>
        <button type="button" className="icon-button" aria-label={t('重新加载')} disabled={busy}
          onClick={() => void browse(storage, location, hidden)}><ArrowClockwise size={17}/></button>
      </form>
    </>}
    <div className="remote-file-list" role="listbox" aria-label={t('服务器文件列表')} aria-busy={busy}>
      {page?.entries.map(entry => <button key={entry.ref.relative_path} role="option" aria-label={entry.name}
        aria-selected={selected?.ref.relative_path === entry.ref.relative_path}
        disabled={busy || !entry.accessible || !['file', 'directory'].includes(entry.kind)}
        className={selected?.ref.relative_path === entry.ref.relative_path ? 'selected' : ''}
        onClick={() => {
          if (entry.kind === 'directory') void browse(entry.ref.storage_id, entry.ref.relative_path, hidden);
          else {setSelected(entry); setPreview(null);}
        }} onDoubleClick={() => {if (entry.kind === 'file') void inspect(entry);}}>
        {entry.kind === 'directory' ? <Folder size={19}/> : <File size={19}/>}<span>{entry.name}</span>
        <small>{entry.kind === 'directory' ? '' : new Intl.NumberFormat().format(entry.size_bytes) + ' B'}</small>
      </button>)}
      {!busy && !roots.length && !error && <p className="results-empty">{t('尚未配置可浏览目录，请联系管理员。')}</p>}
      {!busy && page?.complete && page.entries.length === 0 && <p className="results-empty">{t('此目录为空')}</p>}
      {!busy && page && !page.complete && page.entries.length === 0 && <p className="results-empty">{t('本页没有可显示的文件，可继续浏览下一页。')}</p>}
      {busy && <div className="results-empty"><CircleNotch size={24} className="spin"/></div>}
    </div>
    {page?.next_cursor && <div className="storage-page"><span>{t('按目录顺序显示，每次仅保留当前页。')}</span>
      <button className="subtle-button" disabled={busy} onClick={() => void browse(storage, location, hidden, page.next_cursor!)}>{t('下一页')}</button></div>}
    {preview && <div className="storage-preview"><strong>{preview.entry.name}</strong><pre>{preview.text}</pre>
      {preview.truncated && <p>{t('仅显示文件开头的有限预览。')}</p>}
      {preview.decoding_errors && <p>{t('部分内容无法作为文本显示。')}</p>}
    </div>}
    {error && <p className="field-error" role="alert">{error}</p>}
    <footer><label><input type="checkbox" checked={hidden} disabled={busy || !storage} onChange={event => {
      setHidden(event.target.checked); void browse(storage, location, event.target.checked);
    }}/>{t('显示隐藏文件')}</label>
      <button className="subtle-button" disabled={busy || !selected} onClick={() => {if (selected) void inspect(selected);}}>{t('预览')}</button>
      {onSelect && <button className="primary-button" disabled={busy || !selected} onClick={() => {if (selected) void inspect(selected, true);}}>{t('选择文件')}</button>}
    </footer>
  </section></div>;
}
