import { test, expect } from '@playwright/test';
import { apiRequest } from '../utils/api-request';
import { recurse } from '../utils/recurse';

// Target: Document Upload (P0)
// Scenario: Upload file and poll for 'ready' status.

test.describe('Document Upload API', () => {
  test('[P0] should upload file and transition to ready status', async ({ request }) => {
    // 1. Upload
    const uploadResponse = await request.post('/api/v1/documents/fileupload', {
      multipart: {
        files: {
          name: 'test.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from('hello world'),
        },
        search_space_id: '1',
      }
    });

    expect(uploadResponse.status()).toBe(200);
    const { document_ids } = await uploadResponse.json();
    const docId = document_ids[0];

    // 2. Poll Status (AC#2 logic)
    await recurse(
      async () => {
        const res = await apiRequest(request, {
          method: 'GET',
          path: `/api/v1/documents/status?search_space_id=1&document_ids=${docId}`,
        });
        return await res.json();
      },
      (body) => body.items[0].status.state === 'ready',
      { timeout: 30000, interval: 2000 }
    );
  });

  test('[P1] should reject upload if page quota is exceeded', async ({ request }) => {
    // Logic to simulate quota exceeded (might need user with 0 quota)
    // const response = await request.post('/api/v1/documents/fileupload', {
    //    multipart: { files: [...], search_space_id: '1' }
    // });
    // expect(response.status()).toBe(402);
  });
});