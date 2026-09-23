"use client";

import { useEffect } from "react";
import { buildBackendUrl } from "@/lib/env-config";

// Story 37.6 / AD-120: cookieless engagement beacon for pitch.nowing.ai.
// Tracks visible dwell time, sections viewed (IntersectionObserver on
// [data-pitch-section]) and device type, then ships them with
// navigator.sendBeacon — no cookies, no credentials, no third-party tags.
//
// The backend applies the <3s preview filter and the 30-minute alert
// cooldown; this component just reports: an "open" ping once dwell crosses
// 3s, a heartbeat every 30s while visible, and a "close" ping on leave.

const MIN_DWELL_MS = 3_000;
const HEARTBEAT_MS = 30_000;

function detectDeviceType(): string {
	const ua = navigator.userAgent;
	if (/iPad|Tablet/i.test(ua)) return "tablet";
	if (/Mobi|iPhone|Android/i.test(ua) || window.innerWidth < 768) return "mobile";
	if (window.innerWidth < 1024) return "tablet";
	return "desktop";
}

interface PitchEngagementBeaconProps {
	/** Workspace slug/id as it appears in the portal URL. */
	workspaceRef: string;
	leadId: string;
}

export function PitchEngagementBeacon({ workspaceRef, leadId }: PitchEngagementBeaconProps) {
	useEffect(() => {
		// crypto.randomUUID throws on non-secure contexts/older browsers —
		// fall back so telemetry still works there.
		const sessionId =
			typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
				? crypto.randomUUID()
				: `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
		const sections = new Set<string>();
		let accumulatedMs = 0;
		let visibleSince: number | null =
			document.visibilityState === "visible" ? performance.now() : null;
		let opened = false;
		let closed = false;
		let lastSentDwellMs = 0;

		const endpoint = buildBackendUrl(
			`/api/v1/public/pitch/${encodeURIComponent(workspaceRef)}/${encodeURIComponent(leadId)}/beacon`
		);

		const dwellMs = () =>
			accumulatedMs + (visibleSince === null ? 0 : performance.now() - visibleSince);

		const send = (event: "open" | "heartbeat" | "close") => {
			const body = JSON.stringify({
				dwell_seconds: Math.round(dwellMs() / 100) / 10,
				sections_viewed: [...sections],
				device_type: detectDeviceType(),
				session_id: sessionId,
				event,
			});
			// Plain string body → Content-Type text/plain keeps sendBeacon a
			// "simple" request (no CORS preflight); the API parses raw JSON.
			navigator.sendBeacon(endpoint, body);
		};

		const observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					const id = entry.target.getAttribute("data-pitch-section");
					if (entry.isIntersecting && id) sections.add(id);
				}
			},
			{ threshold: 0.5 }
		);
		for (const el of document.querySelectorAll("[data-pitch-section]")) {
			observer.observe(el);
		}

		// Hidden only pauses dwell accumulation; pagehide sends the single
		// close beacon (the `closed` guard prevents duplicates).
		const sendClose = () => {
			if (closed || !opened) return;
			closed = true;
			send("close");
		};

		const onVisibility = () => {
			if (document.visibilityState === "hidden") {
				if (visibleSince !== null) {
					accumulatedMs += performance.now() - visibleSince;
					visibleSince = null;
				}
			} else if (visibleSince === null) {
				visibleSince = performance.now();
			}
		};

		const onPageHide = () => {
			sendClose();
		};

		const tick = window.setInterval(() => {
			const dwell = dwellMs();
			if (!opened && dwell >= MIN_DWELL_MS) {
				opened = true;
				lastSentDwellMs = dwell;
				send("open");
			} else if (opened && dwell - lastSentDwellMs >= HEARTBEAT_MS) {
				lastSentDwellMs = dwell;
				send("heartbeat");
			}
		}, 1_000);

		document.addEventListener("visibilitychange", onVisibility);
		window.addEventListener("pagehide", onPageHide);
		return () => {
			window.clearInterval(tick);
			observer.disconnect();
			document.removeEventListener("visibilitychange", onVisibility);
			window.removeEventListener("pagehide", onPageHide);
		};
	}, [workspaceRef, leadId]);

	return null;
}
