// The suffix selects the decoder; the server still validates archive contents.
export const ROUTE_FILE_ACCEPT = '.operon.zip';
export const WORKFLOW_FILE_ACCEPT = `${ROUTE_FILE_ACCEPT},.yaml,.yml`;

export function isWorkflowBundle(name: string): boolean {
  return name.toLowerCase().endsWith('.operon.zip') || ['.zip', '.operon'].some(suffix => name.toLowerCase().endsWith(suffix));
}
