import {t} from './i18n';
import {useEffect, useState} from 'react';
import {api} from './api';
import {setPreferences} from './preferences';

/**
 * One profile-wide concurrency default.  A graph that sets its own
 * `max_parallel_tasks` keeps it; everything else uses this number instead of the
 * built-in 2, which is why a 56-core server still ran two operators at a time.
 */
export function ConcurrencySettings() {
  const [value, setValue] = useState(''), [saved, setSaved] = useState(''), [pending, setPending] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    api.preferences().then(preference => {
      if (!live) return;
      const current = preference.parallel_tasks == null ? '' : String(preference.parallel_tasks);
      setValue(current); setSaved(current);
    }).catch(() => { /* The built-in default stays in force. */ });
    return () => {live = false;};
  }, []);
  async function commit() {
    const trimmed = value.trim();
    if (trimmed === saved) return;
    const next = trimmed === '' ? null : Math.max(1, Math.floor(Number(trimmed)));
    if (trimmed !== '' && !Number.isFinite(next)) {setError(t("并发任务数必须是正整数")); return;}
    setPending(true); setError('');
    try {
      const result = await api.savePreferences({parallel_tasks: next});
      setPreferences(result);
      const stored = result.parallel_tasks == null ? '' : String(result.parallel_tasks);
      setValue(stored); setSaved(stored);
    } catch (problem) {setError((problem as Error).message);}
    finally {setPending(false);}
  }
  return <section className="execution-settings">
    <h4>{t("默认并发任务数")}</h4>
    <p className="settings-hint">{t("同一个任务里可以同时运行几步；留空使用内置默认值 2。")}</p>
    <label className="concurrency-field">
      <span className="concurrency-copy">
        <strong>{t("并发任务数")}</strong>
        <small>{t("范围 1–64，上限取决于服务器核数。")}</small>
      </span>
      <input type="number" min={1} max={64} step={1} inputMode="numeric"
        value={value} disabled={pending} placeholder="2"
        onChange={event => setValue(event.target.value)} onBlur={commit} onKeyDown={event => {if (event.key === 'Enter') commit();}}/>
    </label>
    {error && <p className="modal-error" role="alert">{error}</p>}
  </section>;
}
