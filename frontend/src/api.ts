import {t} from './i18n';
import {importErrorMessage} from './importError';
import type { Bootstrap, Graph, Job, Preview, ContractAnalysis, Workspace, SavedWorkflow, WorkflowSummary, RouteDefinition, DataSource } from "./types";
import type { LibraryState, LibraryAction } from "./types";

export type Readiness = {
  status: 'ready' | 'blocked'; fingerprint: string; checked_at: string;
  blocked: {target: string; id: string | null; status: string; message: string}[];
  scope?: 'dependencies' | 'preflight'; dependencies_cached?: boolean; unresolved_sources?: string[];
};
export type CheckFeedback = {signature: string; readiness?: Readiness; error?: string};

export type EnvironmentProgress = {phase?: string; bytes?: number; files?: number; updated_at?: number};
export type EnvironmentStatus = {
  name: string; python: string; spec_sha256: string; interpreter: string; location: string;
  imports: string[]; status: 'missing' | 'stale' | 'ready' | 'failed'; error: string; used_by: string[];
  progress?: EnvironmentProgress | null;
};
export type EnvironmentJob = {
  id: string; name: string; status: 'running' | 'complete' | 'failed';
  error: string | null; started_at: string; finished_at: string | null;
  phase?: string; bytes?: number; files?: number; detail?: string; updated_at?: number;
};
export type RemotePoolJob = {id: string; status?: string; title?: string; updated_at?: string};
export type RemotePool = {
  available?: boolean; unsupported?: boolean; error?: string; running?: boolean;
  version?: string; implementation?: string; closing?: boolean; sessions?: number;
  owner?: {pid?: number}; active_count?: number; active_jobs?: RemotePoolJob[];
  workspaces?: {workspace_id?: string; root?: string; jobs?: number; running?: number}[];
};
export type RemoteEnvironmentProgress = {
  phase?: string; detail?: string; bytes?: number; files?: number; pid?: number;
  updated_at?: string;
};

export type RemoteEnvironment = {
  name?: string; python?: string; status?: string; imports?: string[]; used_by?: string[];
  interpreter?: string; location?: string; error?: string;
  progress?: RemoteEnvironmentProgress | null;
};

export type RemoteEnvironments = {
  root?: string | null; source?: string | null;
  environments?: Record<string, RemoteEnvironment>;
  running?: Record<string, {phase?: string; started_at?: string}>;
  error?: string; started?: string[]; dependencies?: boolean;
};

export type PoolStatus = {
  location: string;
  instance: {version?: string; implementation?: string; address?: number[]; pid?: number; closing: boolean};
  workspaces: {root: string; code_root?: string; jobs: number}[];
  active: {id: string; status: string; title: string; updated_at?: string; workspace: string}[];
  remotes: {profile: {id: string; name: string; host: string}; connected: boolean;
    info?: {build?: {application?: {version?: string}}; library_check?: {replacement_required?: boolean}} | null;
    pool?: RemotePool | null}[];
};
export type EnvironmentSnapshot = {
  root: string; manifest: {path: string; present: boolean};
  environments: Record<string, EnvironmentStatus>; operations: EnvironmentJob[];
};


const base =
  (import.meta as ImportMeta & { env: { VITE_API_BASE?: string } }).env
    .VITE_API_BASE || "";
let token = "";
let workspaceWrite: Promise<unknown> = Promise.resolve();
let preferencesWrite: Promise<unknown> = Promise.resolve();
export class ApiError extends Error {
  constructor(
    message: string,
    public nodeId?: string,
    public status?: number,
    public code?: string,
    public details?: {fingerprint?: string; changed?: boolean},
  ) {
    super(message);
  }
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(token ? { "X-Studio-Token": token } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let value;
  try {
    value = await response.json();
  } catch {
    throw new ApiError(t("本地服务未返回有效响应，请确认服务已启动。"));
  }
  if (!response.ok) {
    const details = Array.isArray(value.detail)
      ? value.detail.map((d: { msg: string }) => d.msg).join("；")
      : value.detail;
    throw new ApiError(
      importErrorMessage(value) || details || t("操作未完成，请重试。"),
      value.node_id,
      response.status,
      value.code,
      value,
    );
  }
  return value as T;
}
export const api = {
  catalogIfChanged: (generation?: string) => request<Bootstrap['catalog'] | null>(`/api/operators${generation ? '?generation=' + encodeURIComponent(generation) : ''}`),
  inspectScript: (payload: {filename: string; code: string; script?: import('./types').ScriptSnapshot}) => request<{script: import('./types').ScriptSnapshot; candidates: {name: string; line: number; schema: Record<string, unknown>}[]}>('/api/scripts/inspect', payload),
  extractScript: (payload: {script: import('./types').ScriptSnapshot; names: string[]}) => request<{script: import('./types').ScriptSnapshot; values: Record<string, unknown>; bindings: unknown}>('/api/scripts/extract', payload),
  publishScript: (payload: {script: import('./types').ScriptSnapshot; operator_id: string; title: string; category: string; version?: string}) => request<{id: string; catalog: Bootstrap['catalog']}>('/api/scripts/publish', payload),
  operatorSource: (id: string) => request<{available: boolean; code?: string; filename?: string; reason?: string}>(`/api/operators/${encodeURIComponent(id)}/source`),
  prepareEnvironment: (graph: Graph) => request<{readiness: Readiness}>('/api/prepare-environment', graph),
  checkEnvironment: (graph: Graph) => request<{readiness: Readiness}>('/api/check-environment', graph),
  environments: () => request<EnvironmentSnapshot>('/api/environments'),
  prepareEnvironments: (names?: string[]) => request<EnvironmentSnapshot & {prepared: {name: string; job: string; status: string}[]}>('/api/environments/prepare', names ? {names} : {}),
  retryEnvironment: (name: string) => request<EnvironmentSnapshot & {job: string}>(`/api/environments/${encodeURIComponent(name)}/retry`, {}),
  environmentLog: (name: string, limit = 200) => request<{name: string; text: string}>(`/api/environments/${encodeURIComponent(name)}/log?limit=${limit}`),
  pool: () => request<PoolStatus>('/api/pool'),
  stopPool: (force = false) =>
    request<{stopped: boolean; forced?: boolean; busy?: boolean; error?: string}>('/api/pool/stop', {force}),
  remotePoolStop: (id: string, force = false) =>
    request<{stopped: boolean; forced?: boolean; busy?: boolean; error?: string}>(
      `/api/remote/${encodeURIComponent(id)}/pool/stop`, {force}),
  remoteEnvironments: (id: string) =>
    request<RemoteEnvironments>(`/api/remote/${encodeURIComponent(id)}/environments`),
  remotePrepareEnvironments: (id: string, names?: string[], dependencies = false) =>
    request<RemoteEnvironments>(`/api/remote/${encodeURIComponent(id)}/environments/prepare`,
      {names, dependencies}),

  savePreferences: (value: Partial<import('./preferences').UiPreferences>, initialize = false) => {
    // Keep responses in edit order when users switch settings sections quickly.
    const result = preferencesWrite.catch(() => {}).then(() => request<import('./preferences').UiPreferences>(`/api/preferences?initialize=${initialize}`, value));
    preferencesWrite = result;
    return result;
  },
  viewers: (refresh = false) => request<import('./viewerTypes').ViewerCatalog>(`/api/v1/viewers?refresh=${refresh}`),
  configureViewer: (id: string, executable: string | null) => request<import('./viewerTypes').ViewerCatalog>(`/api/v1/viewers/${encodeURIComponent(id)}/configure`, {executable}),
  defaultViewer: (extension: string, viewer: string | null) => request<import('./viewerTypes').ViewerCatalog>('/api/v1/viewers/default', {extension, viewer}),
  artifactViewers: (job: string, artifact: string, role: string) => request<import('./viewerTypes').ViewerOptions>(`/api/v1/jobs/${encodeURIComponent(job)}/artifacts/${encodeURIComponent(artifact)}/viewers?role=${encodeURIComponent(role)}`),
  openViewer: (job: string, artifact: string, role: string, viewer?: string) => request<{status: string; mode: string; path: string}>(`/api/v1/jobs/${encodeURIComponent(job)}/artifacts/${encodeURIComponent(artifact)}/open-viewer`, {role, viewer}),
  prepareViewer: (job: string, artifact: string, role: string) => request<{path: string}>(`/api/v1/jobs/${encodeURIComponent(job)}/artifacts/${encodeURIComponent(artifact)}/prepare-viewer`, {role}),
  executionPlan: (graph: Graph) => request<import('./types').ExecutionPlan>('/api/execution/plan', graph),
  executionResources: () => request<import('./types').ExecutionResources>('/api/execution/resources'),
  remoteStatus: () => request<import('./types').RemoteStatus[]>('/api/remote'),
  saveRemote: (profile: import('./types').RemoteProfile) => request<import('./types').RemoteProfile>('/api/remote/profiles', profile),
  connectRemote: (id: string, credentials: {password?: string; passphrase?: string}) => request<import('./types').RemoteInfo>(`/api/remote/${id}/connect`, credentials),
  installRemote: (id: string, credentials: {password?: string; passphrase?: string}, force = false) => request<import('./types').RemoteInfo>(`/api/remote/${id}/install`, {...credentials, force}),
  refreshRemote: (id: string) => request<import('./types').RemoteInfo>(`/api/remote/${id}/refresh`, {}),
  checkRemoteLibrary: (id: string) => request<import('./types').RemoteLibraryCheck>(`/api/remote/${id}/library/check`, {}),
  installRemoteLibrary: (id: string, payload: {packages: string[]; local_revision: string; remote_revision: string}) =>
    request<import('./types').RemoteLibraryOperation>(`/api/remote/${id}/library/install`, payload),
  remoteLibraryStatus: (id: string) => request<import('./types').RemoteLibraryOperation>(`/api/remote/${id}/library/status`),
  remoteSetup: (id: string) => request<{running: boolean; lines: string[]; error: string}>(`/api/remote/${id}/setup`),
  trustRemote: (id: string, fingerprint: string) => request(`/api/remote/${id}/trust`, {fingerprint}),
  disconnectRemote: (id: string) => request(`/api/remote/${id}/disconnect`, {}),
  removeRemote: (id: string) => request(`/api/remote/${id}/remove`, {}),
  browseRemote: (id: string, path: string, offset = 0, hidden = false) => request<import('./types').RemoteListing>(`/api/remote/${id}/browse`, {path, offset, hidden}),
  sourceRemote: (id: string, path: string, reader?: string) => request<{source: DataSource; filename: string; reader: string}>(`/api/remote/${id}/source`, {path, ...(reader ? {reader} : {})}),
  plugins: () => request<import('./types').PluginState>('/api/plugins'),
  refreshPlugins: () => request<import('./types').PluginOperation>('/api/plugins/refresh', {}),
  repairDependencies: () => request<import('./types').PluginOperation>('/api/plugins/dependencies', {}),
  openPluginFolder: (kind: 'operator' | 'reader' | 'extra' = 'operator') => request<{directory: string}>('/api/plugins/open-folder', {kind}),
  pluginOperation: (id: string) => request<import('./types').PluginOperation>(`/api/plugins/operations/${encodeURIComponent(id)}`),
  removePlugin: (name: string) => request<import('./types').PluginOperation>('/api/plugins/remove', {name}),
  managePlugin: (name: string, action: 'enable' | 'disable' | 'restore') => request<import('./types').PluginOperation>('/api/plugins/manage', {name, action}),
  installPlugin: async (file: File): Promise<import('./types').PluginOperation> => {
    const response = await fetch(base + '/api/plugins/install?filename=' + encodeURIComponent(file.name), {
      method: 'POST', headers: {'X-Studio-Token': token, 'Content-Type': 'application/octet-stream'}, body: file,
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.message || result.detail || t("插件安装未完成"));
    return result;
  },
  agent: <T,>(path: string, body?: unknown) => request<T>("/api/agent" + path, body),
  catalog: () => request<Bootstrap["catalog"]>("/api/operators"),
  workspace: () => request<Workspace | null>("/api/workspace"),
  saveWorkspace: (workspace: Workspace) => {
    workspaceWrite = workspaceWrite.catch(() => undefined).then(() => request<{saved: boolean}>("/api/workspace", workspace));
    return workspaceWrite;
  },
  workflows: () => request<WorkflowSummary[]>("/api/workflows"),
  workflow: (id: string) => request<SavedWorkflow>(`/api/workflows/${encodeURIComponent(id)}`),
  prepareWorkflow: (graph: Graph) => request<Graph>("/api/workflows/prepare", graph),
  exportWorkflow: async (graph: Graph, format: 'bundle' | 'yaml' = 'bundle'): Promise<Blob> => {
    const response = await fetch(base + (format === 'yaml' ? '/api/workflows/export-yaml' : '/api/workflows/export'), {
      method: 'POST', headers: {'X-Studio-Token': token, 'Content-Type': 'application/json'}, body: JSON.stringify(graph),
    });
    if (!response.ok) {
      const value = await response.json();
      throw new ApiError(value.message || value.detail || t("路线导出失败"));
    }
    return response.blob();
  },
  importWorkflow: async (file: File): Promise<Graph> => {
    const response = await fetch(base + '/api/workflows/import', {
      method: 'POST', headers: {'X-Studio-Token': token, 'Content-Type': 'application/zip'}, body: file,
    });
    const value = await response.json();
    if (!response.ok) throw new ApiError(value.message || value.detail || t("路线导入失败"));
    return value;
  },
  saveWorkflow: (graph: Graph, id?: string, expected_version?: number) => request<SavedWorkflow>("/api/workflows/save", {graph, id, expected_version}),
  importRouteArchive: async (file: File): Promise<{routes: RouteDefinition[]; failed: {name: string; error: string}[]}> => {
    const response = await fetch(base + '/api/routes/import-archive', {
      method: 'POST', headers: {'X-Studio-Token': token, 'Content-Type': 'application/zip'}, body: file,
    });
    const value = await response.json();
    if (!response.ok) throw new ApiError(value.message || value.detail || t("路线包导入失败"));
    return value;
  },
  routes: () => request<RouteDefinition[]>("/api/routes"),
  libraryState: () => request<LibraryState>("/api/library/state"),
  manageLibrary: (key: string, action: LibraryAction) => request<{routes: RouteDefinition[]; state: LibraryState}>("/api/library/manage", {key, action}),
  registerRoutes: (workflow_ids: string[]) => request<RouteDefinition[]>("/api/routes/register", {workflow_ids}),
  bootstrap: async () => {
    const data = await request<Bootstrap>("/api/bootstrap");
    token = data.token;
    return data;
  },
  validate: (graph: Graph) =>
    request<{ valid: boolean; order: string[]; contracts: ContractAnalysis; readiness: Readiness }>("/api/validate", graph),
  contracts: (graph: Graph) => request<ContractAnalysis>("/api/contracts", graph),
  export: (graph: Graph) =>
    request<{ yaml: string; order: string[] }>("/api/export", graph),
  import: (text: string, base_dir: string) =>
    request<Graph>("/api/import", { text, base_dir }),
  run: (graph: Graph) => request<Job>("/api/jobs", graph),
  history: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  cancel: (id: string) =>
    request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {}),
  preview: (id: string, artifact: string) =>
    request<Preview>(
      `/api/jobs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifact)}/preview`,
    ),
  step: (id: string, index: number) =>
    request<Record<string, unknown>>(
      `/api/jobs/${encodeURIComponent(id)}/exports/${index}`,
    ),
  url: (path: string) => base + path,
  uploadFiles: async (files: File[], base_dir: string, reader?: string) => {
    const batch = await request<{ id: string }>("/api/assets/batches", {filenames: files.map(file => file.name), ...(reader ? {reader} : {})});
    try {
      for (const file of files) await api.upload(file, batch.id);
      return await request<{source: DataSource; filename: string; reader: string; files: string[]}>(
        `/api/assets/batches/${batch.id}/complete`, {base_dir});
    } catch (error) {
      await request(`/api/assets/batches/${batch.id}/cancel`, {}).catch(() => undefined);
      throw error;
    }
  },
  uploadReference: async (file: File, baseDir: string) => {
    const response = await fetch(`${base}/api/assets/reference?filename=${encodeURIComponent(file.name)}&base_dir=${encodeURIComponent(baseDir)}`, {
      method: 'POST', headers: {'Content-Type': 'application/octet-stream', 'X-Studio-Token': token}, body: file,
    });
    const value = await response.json();
    if (!response.ok) throw new ApiError(value.message || value.detail || t("文件导入失败。"));
    return value as {path: string; bytes: number};
  },
  upload: async (file: File, batch?: string) => {
    const response = await fetch(
      `${base}/api/assets?filename=${encodeURIComponent(file.name)}${batch ? `&batch=${encodeURIComponent(batch)}` : ''}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Studio-Token": token,
        },
        body: file,
      },
    );
    const value = await response.json();
    if (!response.ok)
      throw new ApiError(value.message || value.detail || t("上传失败。"));
    return value as { path: string; filename: string; bytes: number };
  },
};
export function downloadText(
  name: string,
  text: string,
  type = "application/json",
) {
  downloadBlob(name, new Blob([text], {type}));
}
export function downloadBlob(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
