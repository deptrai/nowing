import { test, expect } from "../support/merged-fixtures";
import path from "path";

const UNIQUE_SUFFIX = () => Date.now().toString(36);

test.describe("Document Upload Journey", () => {
  test("should upload a file and wait for ready status", async ({ page, authToken, interceptNetworkCall, log }) => {
    const token = authToken;
    const apiUrl = process.env.API_URL || "http://localhost:8000";

    // Setup: Create a search space via API for isolation
    const createResp = await page.request.post(`${apiUrl}/api/searchspaces`, {
      data: { name: `Upload Journey ${UNIQUE_SUFFIX()}`, description: "E2E Test Space" },
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(createResp.status()).toBe(200);
    const { id: spaceId } = await createResp.json();

    // Navigate to dashboard
    await page.goto(`/dashboard/${spaceId}`);

    // Intercept upload API
    const uploadCall = interceptNetworkCall({
      url: "**/api/documents/fileupload",
      method: "POST",
    });

    // Step 1: Select and upload file
    await log({ level: "step", message: "Selecting file for upload" });
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "journey-test.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Content for document upload journey test"),
    });

    const submitBtn = page.getByTestId("upload-submit-button").or(page.getByRole("button", { name: /upload|send/i }));
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    }

    // Step 2: Verify upload success
    const { status } = await uploadCall;
    expect(status).toBe(200);

    // Step 3: Wait for 'Ready' status in UI
    await log({ level: "step", message: "Waiting for document 'Ready' status" });
    
    // The UI should show a processing state then transition to ready
    const docItem = page.getByText("journey-test.txt");
    await expect(docItem).toBeVisible({ timeout: 10000 });

    // Wait for the 'Ready' text or icon associated with the document
    const readyStatus = page.getByText(/ready|done|completed/i).first();
    await expect(readyStatus).toBeVisible({ timeout: 30000 });
  });
});