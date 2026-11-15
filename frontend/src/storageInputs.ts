import type {Catalog, DataSource} from './types';
import type {StorageRef} from './storageTypes';
import {rePointSource} from './readerInput';
import {t} from './i18n';

const quoted = (value: string) => encodeURIComponent(value).replace(/[!'()*]/g,
  character => '%' + character.charCodeAt(0).toString(16).toUpperCase());

export function storageInputPath(ref: StorageRef): string {
  return `storage://${quoted(ref.storage_id)}/${ref.relative_path.split('/').map(quoted).join('/')}`;
}

export function selectStorageInput(previous: DataSource, ref: StorageRef, catalog: Catalog): DataSource {
  if (!ref.version) throw Error(t('请刷新文件列表后重新选择。'));
  const storage_ref = {...ref, format: 'operon.storage-input' as const, schema_version: 1 as const, version: ref.version};
  const source = rePointSource(previous, {...previous, path: storageInputPath(ref), storage_ref, args: {}}, catalog);
  delete source.location;
  return source;
}

export function clearStorageInput(source: DataSource): DataSource {
  const value = {...source};
  delete value.storage_ref;
  return value;
}
