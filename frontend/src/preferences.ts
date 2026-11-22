import {useSyncExternalStore} from 'react';

export type LanguagePreference = 'system' | 'zh-CN' | 'en';
export type ThemePreference = 'system' | 'light' | 'dark';
export type UiPreferences = {language: LanguagePreference; theme: ThemePreference; parallel_tasks?: number | null};
const KEY = 'operon-studio-config-v1';
const defaults: UiPreferences = {language: 'system', theme: 'system'};
const listeners = new Set<() => void>();
function stored(): UiPreferences {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '{}');
    const language = value.language;
    const theme = value.theme;
    const result: UiPreferences = {language: language === 'en' || language === 'zh-CN' ? language : 'system',
      theme: theme === 'light' || theme === 'dark' ? theme : 'system'};
    // An absent key means "use the built-in default", so it is not written back as null.
    const parallel = value.parallel_tasks;
    if (typeof parallel === 'number' && Number.isFinite(parallel) && parallel >= 1) result.parallel_tasks = Math.floor(parallel);
    return result;
  } catch {return defaults;}
}
let current = stored();
export function getPreferences() {return current;}
export function subscribePreferences(listener: () => void) {listeners.add(listener); return () => {listeners.delete(listener);};}
export function setPreferences(value: Partial<UiPreferences>) {
  const next = {...current, ...value};
  if (next.parallel_tasks === null) delete next.parallel_tasks;
  current = next;
  try {localStorage.setItem(KEY, JSON.stringify(current));} catch { /* The profile remains authoritative. */ }
  listeners.forEach(listener => listener());
}
export function usePreferences() {return useSyncExternalStore(subscribePreferences, getPreferences, () => defaults);}
if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === KEY || event.key === null) {current = stored(); listeners.forEach(listener => listener());}
  });
}
