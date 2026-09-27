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

const ZERO_CACHE_PROBE_TIMEOUT_MS = 1_500;

/**
 * Probe whether the zero-cache sync service is reachable before mounting the
 * Zero provider. The browser logs a native "WebSocket connection to ... failed"
 * console error for every failed WS handshake — a log sink cannot suppress it.
 * Skipping the mount entirely when the cache is down keeps the console clean;
 * the app already renders fine without live sync (REST fallback).
 */
async function probeZeroCache(cacheURL: string): Promise<boolean> {
	if (typeof window === "undefined") return true;
	try {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), ZERO_CACHE_PROBE_TIMEOUT_MS);
		try {
			// zero-cache answers GET/HEAD on its base URL (or the /zero proxy path)
			// with anything other than a network failure. Any HTTP response — even
			// 4xx — means the service is up and the WS upgrade is worth attempting.
			//
			// mode:"no-cors": the probe targets the cache's root "/" which is NOT a
			// CORS-enabled endpoint (only /sync/* are). A default "cors" fetch is
			// rejected by the browser even when the service is healthy, making the
			// probe wrongly report the cache as down. With no-cors the response is
			// opaque (status 0) but still resolves — exactly what we need: resolve
			// means reachable, reject means unreachable.
			const res = await fetch(cacheURL, {
				method: "GET",
				mode: "no-cors",
				signal: controller.signal,
				cache: "no-store",
			});
			// Opaque responses have status 0; only a literal 404 (same-origin proxy
			// that couldn't reach upstream) counts as down. In no-cors mode status
			// is always 0, so this check effectively only fires for same-origin.
			return res.status !== 404;
		} finally {
			clearTimeout(timer);
		}
	} catch {
		return false;
	}
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
	// null = probing, false = cache unreachable (render children without Zero),
	// true = reachable (mount Zero provider).
	const [cacheReachable, setCacheReachable] = useState<boolean | null>(null);

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

	useEffect(() => {
		if (!loadedContext || cacheReachable !== null) return;
		let isMounted = true;
		void probeZeroCache(getCacheURL()).then((reachable) => {
			if (isMounted) setCacheReachable(reachable);
		});
		return () => {
			isMounted = false;
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [loadedContext]);

	if (!loadedContext) return null;

	// Wait for the reachability probe before constructing a Zero instance.
	// Children (and their useZero()/useQuery() calls) are not mounted yet, so
	// nothing throws while we resolve. This prevents even the single initial
	// WS handshake error when the cache is down.
	if (cacheReachable === null) return null;

	return (
		<ZeroClientProvider
			userID={loadedContext.context.userId}
			context={loadedContext.context}
			isDesktop={isDesktop}
			initialDesktopAuth={loadedContext.desktopAuth}
			cacheDown={cacheReachable === false}
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
	cacheDown = false,
}: {
	children: React.ReactNode;
	userID: string;
	context: ZeroContext;
	isDesktop: boolean;
	initialDesktopAuth?: string;
	// When true, the zero-cache sync service is unreachable — take the instance
	// offline immediately in init() so it never enters the WS retry loop.
	cacheDown?: boolean;
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
			// init runs right after `new Zero()` — before the first reconnect
			// tick. Going offline here stops the WS retry loop while keeping a
			// valid Zero in context (so useZero()/useQuery() callers don't throw).
			init: cacheDown
				? (z: { close: () => Promise<void> }) => {
						// Close immediately: zero-cache is unreachable. A closed
						// instance still satisfies useZero() and useQuery() (empty
						// snapshot), but never opens the WebSocket — so the browser
						// console stays free of the native ws:// connect errors.
						void z.close();
					}
				: undefined,
		}),
		[userID, context, cacheURL, isDesktop, desktopAuth, cacheDown]
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
