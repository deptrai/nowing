import { faker } from "@faker-js/faker";
import type { APIRequestContext } from "@playwright/test";
import {
	createWorkspace,
	deleteWorkspace,
	type WorkspaceRow,
} from "../../../helpers/api/workspaces";

/**
 * Workspace factory for E2E tests.
 *
 * Creates isolated, uniquely named workspaces and automatically deletes them
 * after the test. Uses Faker for realistic names and descriptions while
 * keeping the generated values greppable in failure traces.
 */
export type WorkspaceFactoryData = {
	name: string;
	description: string;
};

const CREATED: WorkspaceRow[] = [];

export class WorkspaceFactory {
	static defaults(): WorkspaceFactoryData {
		return {
			name: `e2e-${faker.string.alphanumeric(8).toLowerCase()}`,
			description: faker.lorem.sentence(),
		};
	}

	static create(overrides: Partial<WorkspaceFactoryData> = {}): WorkspaceFactoryData {
		return {
			...this.defaults(),
			...overrides,
		};
	}

	static async build(
		request: APIRequestContext,
		token: string,
		overrides: Partial<WorkspaceFactoryData> = {}
	): Promise<WorkspaceRow> {
		const data = this.create(overrides);
		const workspace = await createWorkspace(request, token, data.name, data.description);
		CREATED.push(workspace);
		return workspace;
	}

	static async cleanup(workspace: WorkspaceRow | number): Promise<void> {
		const id = typeof workspace === "number" ? workspace : workspace.id;
		const index = CREATED.findIndex((w) => w.id === id);
		if (index >= 0) CREATED.splice(index, 1);
	}

	static async cleanupAll(request: APIRequestContext, token: string): Promise<void> {
		const ids = CREATED.map((w) => w.id);
		for (const id of ids) {
			try {
				await deleteWorkspace(request, token, id);
			} catch {
				// Ignore: workspace may already be deleted by test teardown.
			}
		}
		CREATED.length = 0;
	}

	static get tracked(): readonly WorkspaceRow[] {
		return CREATED;
	}
}
