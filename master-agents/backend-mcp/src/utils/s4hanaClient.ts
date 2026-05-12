/**
 * S/4HANA HTTP client utility for Basic Auth API calls.
 *
 * Provides a standardized fetch wrapper and response normalization
 * for both OData V4 and V2 endpoints.
 */
import { logDebug, logError } from './logger.js';

export interface S4Config {
  user: string;
  password: string;
  productEndpoint: string;
  stockEndpoint: string;
}

export interface S4Response {
  success: boolean;
  data: unknown;
  count: number;
  total_available?: number;
  request_url?: string;
  error: string | null;
}

/**
 * Read S/4HANA configuration from environment variables.
 * Returns the config or throws descriptive errors for missing vars.
 */
export function getS4Config(): S4Config {
  return {
    user: process.env.S4HANA_USER ?? '',
    password: process.env.S4HANA_PASSWORD ?? '',
    productEndpoint: process.env.S4PRODUCT_ENDPOINT ?? '',
    stockEndpoint: process.env.S4MATERIAL_STOCK_ENDPOINT ?? '',
  };
}

/**
 * Perform an authenticated GET request to an S/4HANA endpoint.
 *
 * @param url   Full URL to fetch
 * @param accept  Accept header value (default: application/json)
 * @returns  Raw fetch Response
 */
export async function s4hanaFetch(
  url: string,
  accept = 'application/json',
): Promise<Response> {
  const { user, password } = getS4Config();
  const auth = Buffer.from(`${user}:${password}`).toString('base64');

  logDebug(`S/4HANA request: ${url}`);

  return fetch(url, {
    method: 'GET',
    headers: {
      Accept: accept,
      Authorization: `Basic ${auth}`,
    },
    signal: AbortSignal.timeout(30_000),
  });
}

/**
 * Make a standard S/4HANA request and return a normalized S4Response.
 * Handles OData V4 collection/single-entity and non-JSON responses.
 */
export async function s4hanaRequest(
  url: string,
  accept = 'application/json',
): Promise<S4Response> {
  try {
    const response = await s4hanaFetch(url, accept);
    const requestUrl = url;

    if (!response.ok) {
      const text = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${text.slice(0, 500)}`,
        data: [],
        count: 0,
        request_url: requestUrl,
      };
    }

    const contentType = response.headers.get('content-type') ?? '';

    // Non-JSON (e.g. $metadata XML)
    if (!contentType.includes('json')) {
      const text = await response.text();
      return {
        success: true,
        data: text,
        count: 1,
        total_available: 1,
        request_url: requestUrl,
        error: null,
      };
    }

    const data = await response.json();

    // OData V4 collection
    if (data.value && Array.isArray(data.value)) {
      return {
        success: true,
        data: data.value,
        count: data.value.length,
        total_available: data['@odata.count'] ?? data.value.length,
        request_url: requestUrl,
        error: null,
      };
    }

    // Single entity
    return {
      success: true,
      data,
      count: 1,
      total_available: 1,
      request_url: requestUrl,
      error: null,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError('S/4HANA request failed', err instanceof Error ? err : new Error(message));

    if (message.includes('TimeoutError') || message.includes('abort')) {
      return { success: false, error: 'Request timed out.', data: [], count: 0 };
    }
    return { success: false, error: `Request failed: ${message}`, data: [], count: 0 };
  }
}

/**
 * Make a request to an OData V2 endpoint and normalize the response.
 * OData V2 wraps collections in `{d: {results: [...]}}` and single entities in `{d: {...}}`.
 */
export async function s4hanaRequestV2(
  url: string,
  accept = 'application/json',
): Promise<S4Response> {
  try {
    const response = await s4hanaFetch(url, accept);
    const requestUrl = url;

    if (!response.ok) {
      const text = await response.text();
      return {
        success: false,
        error: `HTTP ${response.status}: ${text.slice(0, 500)}`,
        data: [],
        count: 0,
        request_url: requestUrl,
      };
    }

    const contentType = response.headers.get('content-type') ?? '';

    if (!contentType.includes('json')) {
      const text = await response.text();
      return {
        success: true,
        data: text,
        count: 1,
        request_url: requestUrl,
        error: null,
      };
    }

    const data = await response.json();

    // OData V2 collection: {d: {results: [...]}}
    if (data.d) {
      const inner = data.d;
      if (typeof inner === 'object' && 'results' in inner && Array.isArray(inner.results)) {
        return {
          success: true,
          data: inner.results,
          count: inner.results.length,
          request_url: requestUrl,
          error: null,
        };
      }
      // OData V2 single entity: {d: {...}}
      return {
        success: true,
        data: [inner],
        count: 1,
        request_url: requestUrl,
        error: null,
      };
    }

    // Fallback
    return {
      success: true,
      data,
      count: 1,
      request_url: requestUrl,
      error: null,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError('S/4HANA V2 request failed', err instanceof Error ? err : new Error(message));

    if (message.includes('TimeoutError') || message.includes('abort')) {
      return { success: false, error: 'Request timed out.', data: [], count: 0 };
    }
    return { success: false, error: `Request failed: ${message}`, data: [], count: 0 };
  }
}
