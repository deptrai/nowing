import { test, expect } from '@playwright/test';
import { apiRequest } from '../utils/api-request';

// Target: RBAC Isolation (P0)
// Scenario: User B should not be able to list or create roles in User A's Search Space.

test.describe('RBAC Isolation API', () => {
  const SEARCH_SPACE_ID_A = 101; // Mocked ID from User A

  test('[P0] User B should be forbidden from listing roles in User A\'s space', async ({ request }) => {
    // Note: authToken fixture should provide User B's context
    const response = await apiRequest(request, {
      method: 'GET',
      path: `/api/v1/searchspaces/${SEARCH_SPACE_ID_A}/roles`,
    });

    expect(response.status()).toBe(403);
    const body = await response.json();
    expect(body.detail).toContain('permission');
  });

  test('[P0] User B should be forbidden from creating roles in User A\'s space', async ({ request }) => {
    const response = await apiRequest(request, {
      method: 'POST',
      path: `/api/v1/searchspaces/${SEARCH_SPACE_ID_A}/roles`,
      data: {
        name: 'Malicious Role',
        permissions: ['*'],
      }
    });

    expect(response.status()).toBe(403);
  });
});