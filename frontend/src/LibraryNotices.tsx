import {FileArrowUp, Package} from '@phosphor-icons/react';
import {t} from './i18n';

/** Fresh 5.0.0 install: explain the two-file order; never download anything. */
export function LibrarySetupGuide({busy, onImport}: {busy?: boolean; onImport: () => void}) {
  return <div className="library-empty-guide">
    <div className="modal-empty"><Package size={30}/><p>{t('尚未安装算子库')}</p></div>
    <p>{t('全新安装的 Operon Studio 不包含算子。请先导入算子库包，再导入路线库包。')}</p>
    <ol>
      <li><strong>{t('算子库：{file}', {file: '.operon-library.zip'})}</strong>
        <span>{t('安装算子、Reader 及其声明环境。')}</span></li>
      <li><strong>{t('路线库：{file}', {file: '.zip'})}</strong>
        <span>{t('包含 routes/*.operon.zip，需与算子库同一版本。')}</span></li>
    </ol>
    <div className="library-empty-actions">
      <button className="primary-button" disabled={busy} onClick={onImport}><FileArrowUp size={16}/>{t('导入算子库')}</button>
      <span>{t('不会自动下载任何文件。')}</span>
    </div>
  </div>;
}

/** A legacy (8.x) library ZIP is rejected before installation: show its message as-is. */
export function LegacyLibraryAlert({message, onChoose}: {message: string; onChoose: () => void}) {
  return <div className="library-legacy-alert" role="alert">
    <strong>{t('无法导入旧版 8.x 算子库')}</strong>
    <pre className="library-legacy-message">{message}</pre>
    <p>{t('当前应用仅接受新版算子库包（.operon-library.zip）。')}</p>
    <p>{t('请先导入算子库 ZIP，再导入路线库 ZIP。')}</p>
    <button className="primary-button" onClick={onChoose}>{t('选择算子库包')}</button>
  </div>;
}
