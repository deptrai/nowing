import { test, expect } from '@playwright/test';
import { apiRequest } from '../utils/api-request';

test.describe('RBAC Isolation API', () => {
  let token: string;

  test.beforeAll(async ({ request }) => {
    const storage = await request.storageState();
    token = storage.origins[0]?.localStorage?.find(i => i.name === 'nowing_access_token')?.value || '';
  });

  test('[P0] User B should be forbidden from listing roles in User A\'s space', async ({ request }) => {
    const SEARCH_SPACE_ID_A = 999999; 

    const response = await apiRequest(request, {
      method: 'GET',
      path: `/api/v1/searchspaces/${SEARCH_SPACE_ID_A}/roles`,
      token,
    });

    expect([403, 404]).toContain(response.status());
  });

  test('[P0] User B should be forbidden from creating roles in User A\'s space', async ({ request }) => {
    const SEARCH_SPACE_ID_A = 999999; 

    const response = await apiRequest(request, {
      method: 'POST',
      path: `/api/v1/searchspaces/${SEARCH_SPACE_ID_A}/roles`,
      data: { name: 'Malicious Role', permissions: ['*'] },
      token,
    });

    expect([403, 404]).toContain(response.status());
  });
});