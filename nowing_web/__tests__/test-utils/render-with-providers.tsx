/**
 * Shared render utility wrapping React Query + Jotai providers.
 * Use this for components that depend on QueryClient or Jotai atoms directly
 * (i.e., when you are NOT mocking jotai/useAtom at module level).
 *
 * For most unit tests, prefer mocking `jotai` at module level instead —
 * that avoids the overhead of real atom state.
 */
import React from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function createTestQueryClient() {
	return new QueryClient({
		defaultOptions: {
			queries: { retry: false, gcTime: 0 },
			mutations: { retry: false },
		},
	});
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
	queryClient?: QueryClient;
}

export function renderWithProviders(
	ui: React.ReactElement,
	{ queryClient = createTestQueryClient(), ...renderOptions }: RenderWithProvidersOptions = {}
) {
	function Wrapper({ children }: { children: React.ReactNode }) {
		return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
	}

	return {
		queryClient,
		...render(ui, { wrapper: Wrapper, ...renderOptions }),
	};
}
