"use client";

import { AlertTriangle, Clock, Hand, Zap } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import type { DshMission, DshMissionControl } from "@/contracts/types/dsh.types";
import { isAllowedUrl } from "@/lib/utils";

export interface HumanLiveTakeoverPopoverProps {
	mission: DshMission;
	missionControl: DshMissionControl;
	resuming?: boolean;
	releasing?: boolean;
	error?: string | null;
	onResume: () => void;
	onRelease: () => void;
}

const TAKEOVER_TTL_SECONDS = 15 * 60;

function formatCountdown(totalSeconds: number): string {
	const seconds = Math.max(0, Math.floor(totalSeconds));
	const m = Math.floor(seconds / 60);
	const s = seconds % 60;
	return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function getChallengeLabel(challenge: string | null | undefined): string {
	if (!challenge) return "CAPTCHA/Challenge";
	const lower = challenge.toLowerCase();
	if (lower.includes("turnstile")) return "Cloudflare Turnstile";
	if (lower.includes("recaptcha")) return "reCAPTCHA";
	if (lower.includes("password")) return "Mật khẩu / 2FA";
	if (lower.includes("otp")) return "Mã OTP";
	if (lower.includes("one-time-code")) return "Mã OTP";
	return "CAPTCHA/Challenge";
}

export const HumanLiveTakeoverPopover: React.FC<HumanLiveTakeoverPopoverProps> = ({
	mission,
	missionControl,
	resuming,
	releasing,
	error,
	onResume,
	onRelease,
}) => {
	const [remainingSeconds, setRemainingSeconds] = useState(TAKEOVER_TTL_SECONDS);

	const expiresAt = useMemo(() => {
		const iso = missionControl?.takeover_expires_at;
		if (iso) {
			const d = new Date(iso);
			if (!Number.isNaN(d.getTime())) return d;
		}
		// Fallback to mission.updated_at + 15 minutes.
		const updated = mission?.updated_at ? new Date(mission.updated_at) : null;
		if (updated && !Number.isNaN(updated.getTime())) {
			return new Date(updated.getTime() + TAKEOVER_TTL_SECONDS * 1000);
		}
		return new Date(Date.now() + TAKEOVER_TTL_SECONDS * 1000);
	}, [missionControl?.takeover_expires_at, mission?.updated_at]);

	const targetUrl = missionControl?.takeover_target_url;
	const challenge = getChallengeLabel(missionControl?.challenge);

	useEffect(() => {
		const tick = () => {
			const remaining = Math.max(0, (expiresAt.getTime() - Date.now()) / 1000);
			setRemainingSeconds(remaining);
		};
		tick();
		const id = setInterval(tick, 1000);
		return () => clearInterval(id);
	}, [expiresAt]);

	const isExpired = remainingSeconds <= 0;

	return (
		<div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 shadow-sm">
			<div className="flex items-start gap-3">
				<div className="mt-0.5 p-1.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 shrink-0">
					<AlertTriangle className="w-4 h-4" />
				</div>
				<div className="flex-1 min-w-0">
					<h3 className="text-sm font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-2">
						<span>Human Live Takeover</span>
						<span className="relative flex h-2 w-2">
							<span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-500 opacity-75" />
							<span className="relative inline-flex rounded-full h-2 w-2 bg-amber-600" />
						</span>
					</h3>
					<p className="text-xs text-amber-700/80 dark:text-amber-400/80 mt-1">
						Agent gặp <strong>{challenge}</strong> tại tab trình duyệt. Hãy xử lý thủ công, sau đó
						trả quyền điều khiển cho agent.
					</p>
					{targetUrl && (
						<p className="text-xs text-amber-700/80 dark:text-amber-400/80 mt-1 truncate">
							Trang:{" "}
							{isAllowedUrl(targetUrl) ? (
								<a
									href={targetUrl}
									target="_blank"
									rel="noopener noreferrer"
									className="underline hover:text-amber-900 dark:hover:text-amber-200"
								>
									{targetUrl}
								</a>
							) : (
								<span>{targetUrl}</span>
							)}
						</p>
					)}
					<div className="mt-2 flex items-center gap-2 text-amber-800 dark:text-amber-300">
						<Clock className="w-3.5 h-3.5" />
						<span className="text-xs font-mono font-semibold tabular-nums">
							{formatCountdown(remainingSeconds)}
						</span>
						<span className="text-[10px] text-amber-700/70 dark:text-amber-400/70">
							{isExpired ? "Đã hết hạn" : "còn lại"}
						</span>
					</div>
					{error && <p className="text-xs text-red-600 mt-2">{error}</p>}
					<div className="mt-3 flex flex-wrap items-center gap-2">
						<button
							type="button"
							disabled={resuming || isExpired}
							onClick={onResume}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-600 hover:bg-amber-700 disabled:bg-amber-400 text-white text-xs font-medium transition-colors"
						>
							<Zap className="w-3.5 h-3.5" />
							{resuming ? "Đang resume..." : "Tiếp tục nhiệm vụ"}
						</button>
						<button
							type="button"
							disabled={releasing}
							onClick={onRelease}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-amber-600/50 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 disabled:opacity-50 text-xs font-medium transition-colors"
						>
							<Hand className="w-3.5 h-3.5" />
							{releasing ? "Đang giữ quyền..." : "Giữ quyền điều khiển"}
						</button>
					</div>
					{isExpired && (
						<p className="text-[10px] text-amber-700/70 dark:text-amber-400/70 mt-2">
							Phiên takeover đã hết hạn. Agent sẽ tự động hủy nhiệm vụ nếu không có hành động.
						</p>
					)}
				</div>
			</div>
		</div>
	);
};
