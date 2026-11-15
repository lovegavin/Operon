import { describe, expect, it } from 'vitest';
import {
  DesktopHostError,
  LEGACY_WIRE,
  createLegacyWireMessage,
  isHostErrorShape,
  toHostError,
} from './types';
import type { HostErrorShape } from './types';

const validShape: HostErrorShape = {
  code: 'host_capability_unavailable',
  message: 'Not available in this host.',
  request_id: null,
  retryable: false,
  next_actions: ['open_host_logs'],
};

describe('DesktopHostError', () => {
  it('serializes every stable field, including Error.message', () => {
    const error = new DesktopHostError(
      'host_capability_unavailable',
      'Full exit is unavailable.',
      'close-7',
      false,
      ['use_tray_menu_exit'],
    );

    expect(error.toJSON()).toEqual({
      code: 'host_capability_unavailable',
      message: 'Full exit is unavailable.',
      request_id: 'close-7',
      retryable: false,
      next_actions: ['use_tray_menu_exit'],
    });
    expect(JSON.parse(JSON.stringify(error))).toEqual(error.toJSON());
  });
});

describe('isHostErrorShape', () => {
  it('accepts a complete valid shape', () => {
    expect(isHostErrorShape(validShape)).toBe(true);
  });

  it('rejects a non-object, unknown code and missing message', () => {
    expect(isHostErrorShape(null)).toBe(false);
    expect(isHostErrorShape('error')).toBe(false);
    expect(isHostErrorShape({ ...validShape, code: 'made_up' })).toBe(false);
    expect(isHostErrorShape({ ...validShape, message: '' })).toBe(false);
    expect(isHostErrorShape({ ...validShape, message: 42 })).toBe(false);
  });

  it('rejects invalid request IDs, retryable and next actions', () => {
    expect(isHostErrorShape({ ...validShape, request_id: 7 })).toBe(false);
    expect(isHostErrorShape({ ...validShape, request_id: '' })).toBe(false);
    expect(isHostErrorShape({ ...validShape, retryable: 'no' })).toBe(false);
    expect(isHostErrorShape({ ...validShape, next_actions: ['run_shell'] })).toBe(false);
    expect(isHostErrorShape({ ...validShape, next_actions: 'retry' })).toBe(false);
  });
});

describe('toHostError', () => {
  it('reconstructs a valid shape and copies its next actions', () => {
    const shape: HostErrorShape = { ...validShape, next_actions: ['open_host_logs'] };
    const normalized = toHostError(shape);
    shape.next_actions.push('retry');

    expect(normalized).toBeInstanceOf(DesktopHostError);
    expect(normalized.toJSON()).toEqual({
      ...validShape,
      next_actions: ['open_host_logs'],
    });
  });

  it('returns an existing DesktopHostError unchanged', () => {
    const error = new DesktopHostError('host_request_stale', 'Stale close request.', 'close-1');
    expect(toHostError(error)).toBe(error);
  });

  it('maps unknown exceptions to a generic bridge failure without leaking them', () => {
    const secret = new Error('C:\\private\\dataset\\token.txt');
    const normalized = toHostError(secret);

    expect(normalized.code).toBe('host_bridge_unavailable');
    expect(normalized.message).toBe('Desktop host bridge failed.');
    expect(normalized.message).not.toContain('private');
    expect(normalized.request_id).toBeNull();
    expect(normalized.retryable).toBe(false);
    expect(normalized.next_actions).toEqual([]);
  });

  it('rejects an incomplete object instead of casting it', () => {
    const normalized = toHostError({ code: 'host_unsupported', message: 'partial' });
    expect(normalized.code).toBe('host_bridge_unavailable');
  });
});

describe('legacy WebView2 wire messages', () => {
  it('has exactly the three one-field objects', () => {
    expect(JSON.stringify(LEGACY_WIRE.studioReady)).toBe('{"type":"studio-ready"}');
    expect(JSON.stringify(LEGACY_WIRE.draftSaved)).toBe('{"type":"draft-saved"}');
    expect(JSON.stringify(LEGACY_WIRE.draftSaveFailed)).toBe('{"type":"draft-save-failed"}');
  });

  it('is immutable at runtime', () => {
    expect(Object.isFrozen(LEGACY_WIRE)).toBe(true);
    expect(Object.isFrozen(LEGACY_WIRE.studioReady)).toBe(true);
    expect(Object.isFrozen(LEGACY_WIRE.draftSaved)).toBe(true);
    expect(Object.isFrozen(LEGACY_WIRE.draftSaveFailed)).toBe(true);
  });

  it('can allocate a fresh message before sending', () => {
    const first = createLegacyWireMessage('draftSaved');
    const second = createLegacyWireMessage('draftSaved');

    expect(first).not.toBe(second);
    expect(first).not.toBe(LEGACY_WIRE.draftSaved);
    expect(first).toEqual({ type: 'draft-saved' });
    expect(Object.keys(first)).toEqual(['type']);
  });
});
