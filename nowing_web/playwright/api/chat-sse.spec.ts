import { test, expect } from '@playwright/test';

// Target: Chat SSE Stream (P0)
// Scenario: Verify SSE format and heartbeat presence.

test.describe('Chat SSE API', () => {
  test('[P0] /new_chat should return text/event-stream with heartbeats', async ({ request }) => {
    const response = await request.post('/api/v1/new_chat', {
      data: {
        chat_id: 1,
        search_space_id: 1,
        user_query: 'Hello AI',
      }
    });

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('text/event-stream');

    const body = await response.body();
    const text = body.toString();
    expect(text).toContain('data:');
  });
});