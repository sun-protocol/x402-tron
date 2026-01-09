/**
 * Tests for encoding utilities
 */

import { describe, it, expect } from 'vitest';
import {
  encodeBase64,
  decodeBase64,
  encodeJSON,
  decodeJSON,
} from '../utils/encoding';

describe('Base64 Encoding', () => {
  it('should encode string to base64', () => {
    const data = 'hello world';
    const encoded = encodeBase64(data);
    expect(encoded).toBe('aGVsbG8gd29ybGQ=');
  });

  it('should decode base64 to string', () => {
    const encoded = 'aGVsbG8gd29ybGQ=';
    const decoded = decodeBase64(encoded);
    expect(decoded).toBe('hello world');
  });

  it('should handle round trip encoding/decoding', () => {
    const original = 'test data 123';
    const encoded = encodeBase64(original);
    const decoded = decodeBase64(encoded);
    expect(decoded).toBe(original);
  });
});

describe('JSON Encoding', () => {
  it('should encode object to JSON string', () => {
    const data = { key: 'value', number: 42 };
    const encoded = encodeJSON(data);
    expect(encoded).toContain('key');
    expect(encoded).toContain('value');
  });

  it('should decode JSON string to object', () => {
    const jsonStr = '{"key":"value","number":42}';
    const decoded = decodeJSON(jsonStr);
    expect(decoded.key).toBe('value');
    expect(decoded.number).toBe(42);
  });

  it('should handle round trip JSON encoding/decoding', () => {
    const original = { test: 'data', nested: { value: 123 } };
    const encoded = encodeJSON(original);
    const decoded = decodeJSON(encoded);
    expect(decoded).toEqual(original);
  });
});
