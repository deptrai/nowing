import { test, expect } from '@playwright/test';
import { apiRequest } from '../utils/api-request';

test.describe('Chat SSE API', () => {
  let token: string;
  let spaceId: number;

  test.beforeAll(async ({ request }) => {
    const storage = await request.storageState();
    token = storage.origins[0]?.localStorage?.find(i => i.name === 'nowing_access_token')?.value || '';
    
    // Create temporary space
    const resp = await apiRequest(request, {
        method: 'POST',
        path: '/api/v1/searchspaces',
        data: { name: `Chat Test ${Date.now()}` },
        token,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    spaceId = body.id;
  });

  test('[P0] /new_chat should return text/event-stream with heartbeats', async ({ request }) => {
    // 1. Create thread - correct endpoint is /api/v1/threads
    const threadResponse = await apiRequest(request, {
        method: 'POST',
        path: '/api/v1/threads',
        data: { 
            title: 'Test Chat',
            search_space_id: spaceId
        },
        token,
    });
    expect(threadResponse.status()).toBe(200);
    const { id: chatId } = await threadResponse.json();

    // 2. Test SSE
    const response = await apiRequest(request, {
      method: 'POST',
      path: '/api/v1/new_chat',
      data: {
        chat_id: chatId,
        search_space_id: spaceId,
        user_query: 'Hello AI',
      },
      token,
    });

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('text/event-stream');

    const body = await response.body();
    expect(body.toString()).toContain('data:');
  });
});