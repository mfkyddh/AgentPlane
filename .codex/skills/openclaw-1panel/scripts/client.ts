import { createHash } from 'node:crypto';
import http from 'node:http';
import https from 'node:https';

import type { OnePanelClientLike, OnePanelResponse, QueryValue, RequestOptions } from './types.js';

export interface OnePanelClientConfig {
  baseUrl: string;
  connectBaseUrl?: string;
  apiKey: string;
  securityEntrance?: string;
  timeoutMs?: number;
  skipTlsVerify?: boolean;
  defaultHeaders?: Record<string, string>;
}

export class OnePanelClient implements OnePanelClientLike {
  private readonly baseUrl: URL;
  private readonly connectBaseUrl: URL;
  private readonly apiKey: string;
  private readonly securityEntrance?: string;
  private readonly timeoutMs: number;
  private readonly skipTlsVerify: boolean;
  private readonly defaultHeaders: Record<string, string>;

  constructor(config: OnePanelClientConfig) {
    this.baseUrl = new URL(config.baseUrl);
    this.connectBaseUrl = new URL(config.connectBaseUrl ?? config.baseUrl);
    this.apiKey = config.apiKey;
    this.securityEntrance = normalizeSecurityEntrance(config.securityEntrance);
    this.timeoutMs = config.timeoutMs ?? 30_000;
    this.skipTlsVerify = config.skipTlsVerify ?? false;
    this.defaultHeaders = config.defaultHeaders ?? {};
  }

  static fromEnv(env: Record<string, string | undefined>): OnePanelClient {
    const baseUrl = env.ONEPANEL_BASE_URL?.trim();
    const apiKey = env.ONEPANEL_API_KEY?.trim();
    if (!baseUrl) {
      throw new Error('Missing ONEPANEL_BASE_URL');
    }
    if (!apiKey) {
      throw new Error('Missing ONEPANEL_API_KEY');
    }

    return new OnePanelClient({
      baseUrl,
      connectBaseUrl: env.ONEPANEL_CONNECT_BASE_URL?.trim(),
      apiKey,
      securityEntrance: env.ONEPANEL_SECURITY_ENTRANCE?.trim(),
      timeoutMs: Number.parseInt(env.ONEPANEL_TIMEOUT_MS || '30000', 10),
      skipTlsVerify: /^(1|true|yes)$/i.test(env.ONEPANEL_SKIP_TLS_VERIFY || ''),
    });
  }

  async request<T = unknown>(options: RequestOptions): Promise<OnePanelResponse<T>> {
    const url = this.buildUrl(options.path, options.query, options.operateNode);
    const body = options.body === undefined ? undefined : JSON.stringify(options.body);
    const headers = this.buildHeaders(body);
    const isHttps = url.protocol === 'https:';
    const transport = isHttps ? https : http;

    return new Promise<OnePanelResponse<T>>((resolve, reject) => {
      const request = transport.request(
        {
          protocol: url.protocol,
          hostname: url.hostname,
          port: url.port || (isHttps ? 443 : 80),
          path: `${url.pathname}${url.search}`,
          method: options.method,
          headers,
          rejectUnauthorized: !this.skipTlsVerify,
          timeout: this.timeoutMs,
        },
        (response) => {
          const chunks: Buffer[] = [];
          response.on('data', (chunk) => {
            chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
          });
          response.on('end', () => {
            const rawBody = Buffer.concat(chunks).toString('utf8');
            const normalizedHeaders = normalizeHeaders(response.headers);
            const data = parseResponseBody<T>(rawBody, normalizedHeaders['content-type']);
            resolve({
              status: response.statusCode ?? 0,
              headers: normalizedHeaders,
              data,
              rawBody,
            });
          });
        },
      );

      request.on('timeout', () => {
        request.destroy(new Error(`1Panel request timed out after ${this.timeoutMs}ms`));
      });
      request.on('error', reject);

      if (body !== undefined) {
        request.write(body);
      }
      request.end();
    });
  }

  private buildUrl(
    path: string,
    query?: Record<string, QueryValue>,
    operateNode?: string,
  ): URL {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    const url = new URL(normalizedPath, this.connectBaseUrl);

    for (const [key, value] of Object.entries(query ?? {})) {
      if (value === undefined || value === null || value === '') {
        continue;
      }
      url.searchParams.set(key, String(value));
    }

    if (operateNode) {
      url.searchParams.set('operateNode', operateNode);
    }

    return url;
  }

  private buildHeaders(body?: string): Record<string, string> {
    return buildOnePanelHeaders({
      apiKey: this.apiKey,
      body,
      origin: this.baseUrl.origin,
      host: this.baseUrl.host,
      securityEntrance: this.securityEntrance,
      defaultHeaders: this.defaultHeaders,
    });
  }
}

export interface BuildOnePanelHeadersConfig {
  apiKey: string;
  body?: string;
  timestamp?: string;
  origin?: string;
  host?: string;
  securityEntrance?: string;
  defaultHeaders?: Record<string, string>;
}

export function buildOnePanelHeaders(
  config: BuildOnePanelHeadersConfig,
): Record<string, string> {
  const timestamp = config.timestamp ?? `${Math.floor(Date.now() / 1000)}`;
  const token = createHash('md5')
    .update(`1panel${config.apiKey}${timestamp}`)
    .digest('hex');

  const headers: Record<string, string> = {
    Accept: 'application/json, text/plain, text/event-stream',
    'Content-Type': 'application/json',
    '1Panel-Token': token,
    '1Panel-Timestamp': timestamp,
    'Content-Length': config.body ? `${Buffer.byteLength(config.body)}` : '0',
  };

  if (config.host) {
    headers.Host = config.host;
  }

  const securityEntrance = normalizeSecurityEntrance(config.securityEntrance);
  if (config.origin && securityEntrance) {
    headers.Origin = config.origin;
    headers.Referer = `${config.origin}/${securityEntrance}/`;
  }

  return {
    ...headers,
    ...(config.defaultHeaders ?? {}),
  };
}

export function normalizeSecurityEntrance(value?: string): string | undefined {
  const normalized = value?.trim().replace(/^\/+|\/+$/g, '');
  return normalized ? normalized : undefined;
}

function normalizeHeaders(headers: http.IncomingHttpHeaders): Record<string, string> {
  const normalized: Record<string, string> = {};
  for (const [key, value] of Object.entries(headers)) {
    if (Array.isArray(value)) {
      normalized[key] = value.join(', ');
      continue;
    }
    if (value !== undefined) {
      normalized[key] = value;
    }
  }
  return normalized;
}

function parseResponseBody<T>(rawBody: string, contentType?: string): T {
  if (contentType?.includes('application/json')) {
    return JSON.parse(rawBody) as T;
  }

  try {
    return JSON.parse(rawBody) as T;
  } catch {
    return rawBody as T;
  }
}
