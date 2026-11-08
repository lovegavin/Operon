import {useState} from 'react';
import {Check, CircleNotch} from '@phosphor-icons/react';
import {api, type CheckFeedback} from './api';
import type {Graph} from './types';
import {t} from './i18n';

export function ReadinessChecks({graph, disabled, preflight, onPreflight}: {
  graph: Graph; disabled: boolean; preflight?: CheckFeedback;
  onPreflight?: (value: CheckFeedback) => void;
}) {
  const signature = JSON.stringify(graph);
  const [environment, setEnvironment] = useState<CheckFeedback>();
  const [localPreflight, setLocalPreflight] = useState<CheckFeedback>();
  const [pending, setPending] = useState('');
  const current = (value?: CheckFeedback) => value?.signature === signature ? value : undefined;
  const checked = current(preflight ?? localPreflight);
  const dependencies = current(environment);
  const issues = checked?.readiness?.status === 'blocked' ? checked.readiness : dependencies?.readiness ?? checked?.readiness;
  async function check(kind: 'dependencies' | 'preflight' | 'repair') {
    setPending(kind);
    let feedback: CheckFeedback;
    try {
      const result = kind === 'preflight' ? await api.validate(graph)
        : kind === 'repair' ? await api.prepareEnvironment(graph) : await api.checkEnvironment(graph);
      feedback = {signature, readiness: result.readiness};
    } catch (error) {feedback = {signature, error: (error as Error).message};}
    if (kind === 'preflight') {
      setLocalPreflight(feedback); onPreflight?.(feedback);
    } else {
      setEnvironment(feedback);
      // Installing dependencies is not a successful preflight. Check data again.
      setLocalPreflight(undefined); onPreflight?.({signature});
    }
    setPending('');
  }
  const locked = disabled || !!pending || !graph.nodes.length;
  return <div className="readiness-checks">
    <div className="execution-preview">
      <button className="subtle-button" disabled={locked} onClick={() => void check('dependencies')}>
        {pending === 'dependencies' ? <CircleNotch size={16} className="spin"/> : <Check size={16}/>}{t('环境依赖检查')}
      </button>
      {dependencies?.readiness && <strong role="status">{dependencies.readiness.status === 'ready' ? t('依赖已就绪') : t('依赖未就绪')}</strong>}
      {dependencies?.error && <p className="field-error" role="alert">{dependencies.error}</p>}
      {!!issues?.unresolved_sources?.length && <p className="helper">{t('未选择 Reader 的输入将在运行前补查')}</p>}
      {issues?.blocked.map((item, index) => <p className="field-error" key={index}>{item.id || item.target}: {item.message}</p>)}
      {issues?.status === 'blocked' && <button className="subtle-button" disabled={locked} onClick={() => void check('repair')}>
        {pending === 'repair' && <CircleNotch size={16} className="spin"/>}{t('安装当前路线所需依赖')}
      </button>}
    </div>
    <div className="execution-preview">
      <button className="subtle-button" disabled={locked} onClick={() => void check('preflight')}>
        {pending === 'preflight' ? <CircleNotch size={16} className="spin"/> : <Check size={16}/>}{t('运行前检查')}
      </button>
      {checked?.readiness && <strong role="status">{checked.readiness.status === 'ready' ? t('运行前检查通过') : t('依赖未就绪')}</strong>}
      {checked?.error && <p className="field-error" role="alert">{checked.error}</p>}
    </div>
  </div>;
}
