import { test, expect } from '@playwright/test';
import { apiRequest } from '../utils/api-request';
import { recurse } from '../utils/recurse';

test.describe('Document Upload API', () => {
  let token: string;
  let spaceId: number;

  test.beforeAll(async ({ request }) => {
    const storage = await request.storageState();
    token = storage.origins[0]?.localStorage?.find(i => i.name === 'nowing_access_token')?.value || '';
    
    // Explicitly using /api/v1 prefix
    const resp = await apiRequest(request, {
        method: 'POST',
        path: '/api/v1/searchspaces',
        data: { name: `Upload Test ${Date.now()}`, description: 'Temporary' },
        token,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    spaceId = body.id;
  });

  test('[P0] should upload file successfully', async ({ request }) => {
    // 1. Upload
    const uploadResponse = await apiRequest(request, {
      method: 'POST',
      path: '/api/v1/documents/fileupload',
      multipart: {
        files: {
          name: 'test.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('hello world'),
        },
        search_space_id: spaceId.toString(),
      },
      token,
    });

    expect(uploadResponse.status()).toBe(200);
    const body = await uploadResponse.json();
    expect(body).toHaveProperty('document_ids');
  });
});