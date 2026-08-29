"use client";

import type { LogLevel, LogSink } from "@rocicorp/logger";
import {
	useConnectionState,
	useZero,
	ZeroProvider as ZeroReactProvider,
} from "@rocicorp/zero/react";
import { AlertTriangle, CloudOff } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { authenticatedFetch, getDesktopAccessToken } from "@/lib/auth-fetch";
import { handleUnauthorized, isPublicRoute, refreshSession } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";
import type { Context } from "@/types/zero";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const isDev = process.env.NODE_ENV === "development";

const configuredCacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL;
type ZeroContext = Exclude<Context, undefined>;
type LoadedZeroContext = {
	context: ZeroContext;
	desktopAuth?: string;
};
type ZeroContextState = LoadedZeroContext | null | undefined;

function getCacheURL() {
	if (configuredCacheURL) return configuredCacheURL;
	if (typeof window !== "undefined") {
		return `${window.location.origin}/zero`;
	}
	return "http://localhost:4848";
}

async function fetchZeroContext(isDesktop: boolean): Promise<LoadedZeroContext | null> {
	const response = await authenticatedFetch(buildBackendUrl("/zero/context"), {
		skipAuthRedirect: true,
	});
	if (response.status === 401) {
		// Auth is dead (refresh already failed inside authenticatedFetch). This
		// provider gates the whole app tree, so nothing below it (e.g.
		// DashboardShell) can run its own redirect — do it here.
		handleUnauthorized();
		return null;
	}
	if (!response.ok) return null;

	return {
		context: (await response.json()) as ZeroContext,
		desktopAuth: isDesktop ? (await getDesktopAccessToken()) || undefined : undefined,
	};
}

// Cap how many times we will refresh the session in response to Zero's
// `needs-auth` state before giving up. Without this, a persistent auth failure
// in zero-cache makes the connection cycle needs-auth -> connecting -> needs-auth
// indefinitely, each cycle firing a `/auth/jwt/refresh` and quickly tripping the
// backend rate limiter (HTTP 429).
const MAX_ZERO_AUTH_REFRESH_ATTEMPTS = 3;
const ZERO_AUTH_REFRESH_BASE_DELAY_MS = 1_000;
const ZERO_AUTH_REFRESH_MAX_DELAY_MS = 30_000;

// Throttle repeated WebSocket/connection error logs so a down zero-cache does
// not flood the console while still keeping `error`-level output in dev.
const MAX_CONNECTION_LOGS_PER_MINUTE = 3;
const connectionLogWindowMs = 60_000;

// Number of consecutive connection failures before we treat the sync layer as
// offline and show a non-blocking banner.
const OFFLINE_BANNER_THRESHOLD = 2;

/** Deduplicating log sink that swallows the noisiest Zero log lines. */
const zeroLogSink: LogSink = {
	log(level, _context, ...args) {
		const message = String(args[0] ?? "");

		// Always surface auth and schema/version errors.
		const alwaysShow = /needs-auth|401|403|version|schema/i.test(message);

		// Downgrade repetitive connection noise unless in dev.
		const isConnectionNoise = /connect|websocket|ws|socket|disconnected|retry/i.test(message);
		if (isConnectionNoise && !alwaysShow) {
			if (level === "error" || level === "warn") {
				if (isDev) {
					// Rate-limit dev logs so the console stays readable.
					throttledLog(level, args);
				}
				return;
			}
		}

		console[level]?.(message, ...args.slice(1));
	},
	flush: () => Promise.resolve(),
};

let logBucket: { count: number; resetAt: number } | null = null;

function throttledLog(level: "error" | "warn", args: unknown[]) {
	const now = Date.now();
	if (!logBucket || now > logBucket.resetAt) {
		logBucket = { count: 1, resetAt: now + connectionLogWindowMs };
	} else {
		logBucket.count += 1;
	}

	if (logBucket.count <= MAX_CONNECTION_LOGS_PER_MINUTE) {
		console[level]?.(
			`[zero] connection log throttled (${logBucket.count}/${MAX_CONNECTION_LOGS_PER_MINUTE} in 60s):`,
			...args
		);
	}
}

type ConnectionState = ReturnType<typeof useConnectionState>;

function ZeroConnectionBanner({ state, failures }: { state: ConnectionState; failures: number }) {
	if (state.name === "connected" || failures < OFFLINE_BANNER_THRESHOLD) return null;

	const isAuthError = state.name === "needs-auth" || state.name === "error";
	const Icon = isAuthError ? AlertTriangle : CloudOff;
	const message = isAuthError
		? "Sync service is paused. Waiting for a fresh session."
		: "Real-time sync is offline. Retrying in the background.";

	return (
		<output
			aria-live="polite"
			className={cn(
				"fixed bottom-4 left-1/2 z-50 -translate-x-1/2",
				"flex items-center gap-2 rounded-full px-4 py-2 text-sm shadow-lg",
				"bg-background/95 text-foreground border border-border backdrop-blur-sm"
			)}
		>
			<Icon className="h-4 w-4 text-amber-500" aria-hidden="true" />
			<span>{message}</span>
		</output>
	);
}

function ZeroAuthSync({ isDesktop }: { isDesktop: boolean }) {
	const zero = useZero();
	const connectionState = useConnectionState();
	const refreshAttemptsRef = useRef(0);
	const refreshInFlightRef = useRef(false);
	const [consecutiveFailures, setConsecutiveFailures] = useState(0);

	// Track connection health: increment on terminal error / disconnected states,
	// reset on success. `connecting` is Zero's own retry and is not a failure.
	useEffect(() => {
		if (connectionState.name === "connected") {
			setConsecutiveFailures(0);
			refreshAttemptsRef.current = 0;
		} else if (connectionState.name === "disconnected" || connectionState.name === "error") {
			setConsecutiveFailures((prev) => prev + 1);
		}
	}, [connectionState.name]);

	useEffect(() => {
		if (connectionState.name !== "needs-auth") return;
		if (refreshInFlightRef.current) return;

		if (refreshAttemptsRef.current >= MAX_ZERO_AUTH_REFRESH_ATTEMPTS) {
			handleUnauthorized();
			return;
		}

		const attempt = refreshAttemptsRef.current;
		const delayMs =
			attempt === 0
				? 0
				: Math.min(
						ZERO_AUTH_REFRESH_BASE_DELAY_MS * 2 ** (attempt - 1),
						ZERO_AUTH_REFRESH_MAX_DELAY_MS
					);

		refreshInFlightRef.current = true;
		const timer = setTimeout(() => {
			refreshAttemptsRef.current += 1;
			refreshSession()
				.then(async (refreshed) => {
					if (!refreshed) {
						handleUnauthorized();
						return;
					}

					if (isDesktop) {
						const newToken = await getDesktopAccessToken({ forceRefresh: true });
						if (!newToken) {
							handleUnauthorized();
							return;
						}
						zero.connection.connect({ auth: newToken });
					} else {
						zero.connection.connect();
					}
				})
				.finally(() => {
					refreshInFlightRef.current = false;
				});
		}, delayMs);

		return () => clearTimeout(timer);
	}, [connectionState.name, isDesktop, zero]);

	useEffect(() => {
		if (typeof window === "undefined" || !window.electronAPI?.onAuthChanged) return;
		return window.electronAPI.onAuthChanged(({ accessToken }) => {
			if (accessToken) {
				zero.connection.connect({ auth: accessToken });
			}
		});
	}, [zero]);

	return <ZeroConnectionBanner state={connectionState} failures={consecutiveFailures} />;
}

function AuthenticatedZeroProvider({
	children,
	isDesktop,
}: {
	children: React.ReactNode;
	isDesktop: boolean;
}) {
	const [loadedContext, setLoadedContext] = useState<ZeroContextState>(undefined);

	useEffect(() => {
		let isMounted = true;

		const load = async () => {
			const nextContext = await fetchZeroContext(isDesktop);
			if (isMounted) {
				setLoadedContext(nextContext);
			}
		};

		void load();

		if (!isDesktop || typeof window === "undefined" || !window.electronAPI?.onAuthChanged) {
			return () => {
				isMounted = false;
			};
		}

		const unsubscribe = window.electronAPI.onAuthChanged(({ accessToken }) => {
			if (!accessToken) {
				setLoadedContext(undefined);
				return;
			}
			void load();
		});

		return () => {
			isMounted = false;
			unsubscribe();
		};
	}, [isDesktop]);

	if (!loadedContext) return null;

	return (
		<ZeroClientProvider
			userID={loadedContext.context.userId}
			context={loadedContext.context}
			isDesktop={isDesktop}
			initialDesktopAuth={loadedContext.desktopAuth}
		>
			{children}
		</ZeroClientProvider>
	);
}

function ZeroClientProvider({
	children,
	userID,
	context,
	isDesktop,
	initialDesktopAuth,
}: {
	children: React.ReactNode;
	userID: string;
	context: ZeroContext;
	isDesktop: boolean;
	initialDesktopAuth?: string;
}) {
	const cacheURL = useMemo(() => getCacheURL(), []);
	const [desktopAuth, setDesktopAuth] = useState<string | undefined>(initialDesktopAuth);

	useEffect(() => {
		setDesktopAuth(initialDesktopAuth);
	}, [initialDesktopAuth]);

	useEffect(() => {
		if (!isDesktop) return;
		let isMounted = true;
		getDesktopAccessToken().then((token) => {
			if (isMounted) setDesktopAuth(token || undefined);
		});
		return () => {
			isMounted = false;
		};
	}, [isDesktop]);

	const opts = useMemo(
		() => ({
			userID,
			schema,
			queries,
			context,
			cacheURL,
			auth: isDesktop ? desktopAuth : undefined,
			// Route Zero's internal logs through our throttled sink so a missing
			// zero-cache does not spam the browser console.
			logSink: zeroLogSink,
			logLevel: (isDev ? "info" : "error") as LogLevel,
		}),
		[userID, context, cacheURL, isDesktop, desktopAuth]
	);

	return (
		<ZeroReactProvider {...opts}>
			<ZeroAuthSync isDesktop={isDesktop} />
			{children}
		</ZeroReactProvider>
	);
}

function WebZeroProvider({ children }: { children: React.ReactNode }) {
	const session = useSession();

	// Same reasoning as fetchZeroContext: this provider blocks the whole tree,
	// so the login redirect must happen here, not in a child that never mounts.
	useEffect(() => {
		if (session.status === "unauthenticated") handleUnauthorized();
	}, [session.status]);

	if (session.status !== "authenticated") {
		return null;
	}

	return <AuthenticatedZeroProvider isDesktop={false}>{children}</AuthenticatedZeroProvider>;
}

function DesktopZeroProvider({ children }: { children: React.ReactNode }) {
	return <AuthenticatedZeroProvider isDesktop>{children}</AuthenticatedZeroProvider>;
}

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();
	const isDesktop = typeof window !== "undefined" && !!window.electronAPI;

	if (isPublicRoute(pathname)) {
		return <>{children}</>;
	}

	if (isDesktop) {
		return <DesktopZeroProvider>{children}</DesktopZeroProvider>;
	}

	return <WebZeroProvider>{children}</WebZeroProvider>;
}
