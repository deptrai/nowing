import { APIRequestContext, APIResponse } from '@playwright/test';

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  data?: any;
  headers?: { [key: string]: string };
  multipart?: { [key: string]: any };
}

/**
 * Enhanced API request helper with automatic prefix and optional logging.
 */
export async function apiRequest(
  request: APIRequestContext,
  options: ApiRequestOptions
): Promise<APIResponse> {
  const { method = 'GET', path, data, headers, multipart } = options;
  
  // Ensure path starts with /
  const url = path.startsWith('/') ? path : `/${path}`;

  return await request.fetch(url, {
    method,
    data,
    headers,
    multipart,
  });
}
