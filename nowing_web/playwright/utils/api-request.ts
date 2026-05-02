import { APIRequestContext, APIResponse } from '@playwright/test';

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  data?: any;
  headers?: { [key: string]: string };
  multipart?: { [key: string]: any };
  token?: string;
}

/**
 * Enhanced API request helper with automatic prefix and optional logging.
 */
export async function apiRequest(
  request: APIRequestContext,
  options: ApiRequestOptions
): Promise<APIResponse> {
  const { method = 'GET', path, data, headers = {}, multipart, token } = options;
  
  // Ensure path starts with /
  const url = path.startsWith('/') ? path : `/${path}`;
  
  // Debug log
  console.log(`[API Request] ${method} ${url}`);

  const requestHeaders = { ...headers };
  if (token) {
    requestHeaders['Authorization'] = `Bearer ${token}`;
  }

  const response = await request.fetch(url, {
    method,
    data,
    headers: requestHeaders,
    multipart,
  });

  if (!response.ok()) {
      console.error(`[API Error] ${response.status()} ${response.statusText()} for ${url}`);
  }

  return response;
}
