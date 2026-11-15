export type StorageRef = {
  storage_id: string;
  relative_path: string;
  version?: string | null;
  digest?: string | null;
};

export type StorageInputRef = StorageRef & {
  format: 'operon.storage-input'; schema_version: 1; version: string;
};

export type StorageEntry = {
  ref: StorageRef;
  name: string;
  kind: 'file' | 'directory' | 'symlink' | 'other';
  size_bytes: number;
  modified_ns: number | null;
  is_symlink: boolean;
  accessible: boolean;
};

export type StorageBrowseRequest = {
  storage_id: string;
  relative_path: string;
  cursor?: string | null;
  hidden: boolean;
  order: 'filesystem';
};

export type StoragePage = {
  entries: StorageEntry[];
  next_cursor: string | null;
  listing_revision: string;
  complete: boolean;
  order: 'filesystem';
  scanned: number;
};

export type StoragePreview = {
  entry: StorageEntry;
  text: string;
  bytes_read: number;
  rows: number;
  truncated: boolean;
  decoding_errors: boolean;
};
