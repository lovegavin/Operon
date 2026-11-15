import {request, requestFile} from './api';
import type {BindingOptions, BoundInput, ExportReceipt, PlanArtifact, PlanAttempt, PlanBinding, PlanCompile,
  PlanEvents, PlanExportRequest, PlanFile, PlanFilePreview, PlanLog, PlanPage, PlanReceipt, PlanSubmission,
  PlanUiState, RunPlan} from './planTypes';
const path = (run: string) => `/api/v1/plans/${encodeURIComponent(run)}`;
const page = (after: string) => `after=${encodeURIComponent(after)}&limit=30&max_bytes=16384`;
export const planApi = {
  compile: (payload: PlanCompile, signal?: AbortSignal) => request<RunPlan>('/api/v1/plans/compile', payload, {signal}),
  bindingOptions: (plan: RunPlan, binding: Partial<PlanBinding>, signal?: AbortSignal, input_paths?: Record<string, Pick<BoundInput, 'path' | 'representation'>>) => request<BindingOptions>(
    '/api/v1/plans/binding-options', {plan, package_root: binding.package_root || '.',
      ...(binding.environment_store ? {environment_store: binding.environment_store} : {}), ...(input_paths ? {input_paths} : {})}, {signal}),
  state: (signal?: AbortSignal) => request<PlanUiState>('/api/v1/plan-ui-state', undefined, {signal}),
  saveState: (state: PlanUiState, signal?: AbortSignal) => request<PlanUiState>('/api/v1/plan-ui-state', state, {signal}),
  submit: (value: PlanSubmission, signal?: AbortSignal) => request<PlanReceipt>('/api/v1/plans', value, {signal}),
  details: (run: string, signal?: AbortSignal) => request<PlanReceipt>(path(run), undefined, {signal}),
  cancel: (run: string, signal?: AbortSignal) => request<PlanReceipt>(`${path(run)}/cancel`, {}, {signal}),
  events: (run: string, after = 0, signal?: AbortSignal) => request<PlanEvents>(`${path(run)}/events?after=${after}&limit=30&max_bytes=16384`, undefined, {signal}),
  attempts: (run: string, after = '', signal?: AbortSignal) => request<PlanPage<PlanAttempt, 'attempts'>>(`${path(run)}/attempts?${page(after)}`, undefined, {signal}),
  artifacts: (run: string, after = '', signal?: AbortSignal) => request<PlanPage<PlanArtifact, 'artifacts'>>(`${path(run)}/artifacts?${page(after)}`, undefined, {signal}),
  logs: (run: string, attempt: string, offset = 0, signal?: AbortSignal) => request<PlanLog>(`${path(run)}/logs?attempt_id=${encodeURIComponent(attempt)}&offset=${offset}&max_bytes=16384&encoding=text`, undefined, {signal}),
  files: (run: string, artifact: string, after = '', signal?: AbortSignal) => request<PlanPage<PlanFile, 'files'>>(`${path(run)}/artifacts/${encodeURIComponent(artifact)}/files?${page(after)}`, undefined, {signal}),
  preview: (run: string, artifact: string, file: string, signal?: AbortSignal) => request<PlanFilePreview>(`${path(run)}/artifacts/${encodeURIComponent(artifact)}/files/${encodeURIComponent(file)}/preview?max_bytes=16384&max_rows=200`, undefined, {signal}),
  open: (run: string, artifact: string, file: string, signal?: AbortSignal) => requestFile(`${path(run)}/artifacts/${encodeURIComponent(artifact)}/files/${encodeURIComponent(file)}/open`, signal),
  export: (value: PlanExportRequest, signal?: AbortSignal) => request<ExportReceipt>('/api/v1/plan-exports', value, {signal}),
  exportDetails: (id: string, signal?: AbortSignal) => request<ExportReceipt>(`/api/v1/plan-exports/${encodeURIComponent(id)}`, undefined, {signal}),
  exportLookup: (key: string, signal?: AbortSignal) => request<ExportReceipt>(`/api/v1/plan-exports/lookup?request_id=${encodeURIComponent(key)}`, undefined, {signal}),
  cancelExport: (id: string, signal?: AbortSignal) => request<ExportReceipt>(`/api/v1/plan-exports/${encodeURIComponent(id)}/cancel`, {}, {signal}),
};
