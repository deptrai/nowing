import { faker } from "@faker-js/faker";

/**
 * Test user factory for E2E authentication fixtures.
 *
 * Generates deterministic, realistic, local-only test credentials. These
 * values are intentionally fake and are only used against the local E2E
 * backend with E2E-minted tokens.
 */
export type UserFactoryData = {
	email: string;
	password: string;
	displayName: string;
};

export class UserFactory {
	static defaults(): UserFactoryData {
		return {
			email: "e2e-test@nowing.net",
			password: "E2eTestPassword123!",
			displayName: "E2E Test User",
		};
	}

	static create(overrides: Partial<UserFactoryData> = {}): UserFactoryData {
		return {
			...this.defaults(),
			...overrides,
		};
	}

	static random(prefix = "e2e"): UserFactoryData {
		return {
			email: `${prefix}-${faker.string.alphanumeric(8).toLowerCase()}@nowing.net`,
			password: `E2e_${faker.internet.password({ length: 16, memorable: false })}!`,
			displayName: `${faker.person.firstName()} ${faker.person.lastName()}`,
		};
	}

	/**
	 * No remote cleanup required: users are either the shared seeded test
	 * user or created via the E2E-only /__e2e__/auth/token endpoint.
	 */
	static async cleanup(_data: UserFactoryData): Promise<void> {
		// Intentionally no-op for the E2E harness.
	}
}
