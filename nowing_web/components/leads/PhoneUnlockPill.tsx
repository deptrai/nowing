"use client";

import { useAtom, useAtomValue } from "jotai";
import { Check, Phone } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { fastUnlockSessionAtom, makeFastUnlockKey } from "@/atoms/leads/leads-canvas.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { Lead } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn, copyToClipboard } from "@/lib/utils";
import { SmartUnlockPopover } from "./SmartUnlockPopover";

const UNLOCK_COST_CREDITS = 1.5;
const FAST_UNLOCK_TTL_MS = 30 * 60 * 1000;

export interface PhoneUnlockPillProps {
	lead: Lead;
	workspaceId: number | string;
	className?: string;
	showIcon?: boolean;
	onUnlock?: (unlocked: boolean) => void;
}

export const PhoneUnlockPill: React.FC<PhoneUnlockPillProps> = ({
	lead,
	workspaceId,
	className,
	showIcon = true,
	onUnlock,
}) => {
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const [fastUnlockSessions, setFastUnlockSessions] = useAtom(fastUnlockSessionAtom);

	const [isUnlocked, setIsUnlocked] = useState(lead.is_unlocked);
	const [displayPhone, setDisplayPhone] = useState(lead.phone ?? "");
	const [copied, setCopied] = useState(false);
	const [isOpen, setIsOpen] = useState(false);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const [fastUnlockEnabled, setFastUnlockEnabled] = useState(false);
	const [isFlipped, setIsFlipped] = useState(false);
	const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		setIsUnlocked(lead.is_unlocked);
		setDisplayPhone(lead.phone ?? "");
	}, [lead.is_unlocked, lead.phone]);

	useEffect(() => {
		return () => {
			if (copyTimerRef.current) {
				clearTimeout(copyTimerRef.current);
			}
		};
	}, []);

	const contactId = lead.contact_id;
	const isDnc = lead.consent_status === "withdrawn";
	const isInvalid = lead.is_valid === false;
	const isDisabled = !contactId || isDnc || isInvalid;

	const fastUnlockKey = makeFastUnlockKey(workspaceId, currentUser?.id);
	const sessionState = fastUnlockSessions[fastUnlockKey];
	const isFastUnlockActive = !!sessionState && sessionState.expires_at > Date.now();

	const safePhone = (displayPhone || "").trim();
	const isMasked = safePhone.includes("*");
	const isPhoneValid =
		Boolean(safePhone) && !safePhone.includes("|") && !safePhone.includes("Website");

	if (!isPhoneValid) {
		if (lead.is_new_from_zero) {
			return (
				<span className="text-emerald-600/80 text-xs font-medium animate-pulse select-none">
					Đang giải mã SĐT...
				</span>
			);
		}
		return <span className="text-muted-foreground/40 text-xs select-none">—</span>;
	}

	const handleCopy = async (e: React.MouseEvent | React.KeyboardEvent) => {
		e.stopPropagation();
		e.preventDefault();
		if (copied || isMasked || !safePhone) return;

		const normalized = safePhone.replace(/[^\d+]/g, "");
		const success = await copyToClipboard(normalized || safePhone);
		if (success) {
			setCopied(true);
			toast.success(`Đã copy SĐT ${safePhone}!`, { duration: 1500 });
			if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
			copyTimerRef.current = setTimeout(() => setCopied(false), 1500);
		} else {
			toast.error("Không thể copy số điện thoại");
		}
	};

	const applyFastUnlockSession = (enabled: boolean) => {
		if (!enabled) {
			setFastUnlockSessions((prev) => {
				const next = { ...prev };
				delete next[fastUnlockKey];
				return next;
			});
			return;
		}
		setFastUnlockSessions((prev) => ({
			...prev,
			[fastUnlockKey]: { expires_at: Date.now() + FAST_UNLOCK_TTL_MS },
		}));
	};

	const performUnlock = async () => {
		if (!contactId || isUnlocking) return;
		setIsUnlocking(true);
		try {
			const res = await leadsApiService.unlockContact(workspaceId, lead.id, contactId);
			setIsUnlocked(true);
			onUnlock?.(true);
			setDisplayPhone(res.phone ?? res.phone ?? displayPhone);
			setIsFlipped(true);
			setTimeout(() => setIsFlipped(false), 300);

			toast.success(`Đã mở khóa SĐT -${UNLOCK_COST_CREDITS} credits`, {
				duration: 5000,
				action: {
					label: "Hoàn tác",
					onClick: () => void performRelock(),
				},
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : "Không thể mở khóa";
			toast.error(message);
		} finally {
			setIsUnlocking(false);
			setIsOpen(false);
		}
	};

	const performRelock = async () => {
		if (!contactId) return;
		try {
			const res = await leadsApiService.relockContact(workspaceId, lead.id, contactId);
			setIsUnlocked(false);
			onUnlock?.(false);
			setDisplayPhone(res.phone ?? displayPhone);
			toast.success("Đã hoàn tác mở khóa");
			applyFastUnlockSession(false);
		} catch (err) {
			const message = err instanceof Error ? err.message : "Không thể hoàn tác";
			toast.error(message);
		}
	};

	const handlePillClick = (e: React.MouseEvent) => {
		e.stopPropagation();
		if (isDisabled) return;

		if (isUnlocked) {
			void handleCopy(e);
			return;
		}

		if (isFastUnlockActive) {
			void performUnlock();
			return;
		}

		setFastUnlockEnabled(isFastUnlockActive);
		setIsOpen(true);
	};

	const handleConfirm = () => {
		applyFastUnlockSession(fastUnlockEnabled);
		void performUnlock();
	};

	const pillContent = (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-xs font-mono font-medium transition-all duration-150 cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50",
				copied
					? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-xs"
					: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/40",
				isFlipped && "animate-flip",
				isDisabled && "opacity-50 cursor-not-allowed",
				className
			)}
			data-testid={contactId ? `phone-pill-${contactId}` : undefined}
		>
			{showIcon && (
				<span className="shrink-0">
					{copied ? (
						<Check className="size-3.5 text-emerald-600 dark:text-emerald-400 animate-in zoom-in-50" />
					) : (
						<Phone className="size-3.5 text-emerald-600 dark:text-emerald-400" />
					)}
				</span>
			)}
			<span className="tabular-nums tracking-tight">{safePhone}</span>
			{copied && (
				<span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-sans ml-0.5 font-bold">
					✓
				</span>
			)}
		</span>
	);

	if (isUnlocked) {
		return (
			<button
				type="button"
				aria-label={`Copy phone number ${safePhone}`}
				title={copied ? "Đã copy" : `Click để copy: ${safePhone}`}
				onClick={handlePillClick}
				className="inline-flex"
			>
				{pillContent}
			</button>
		);
	}

	return (
		<SmartUnlockPopover
			open={isOpen}
			onOpenChange={setIsOpen}
			maskedPhone={safePhone}
			costCredits={UNLOCK_COST_CREDITS}
			fastUnlockEnabled={fastUnlockEnabled}
			onToggleFastUnlock={setFastUnlockEnabled}
			onConfirm={handleConfirm}
			onCancel={() => setIsOpen(false)}
		>
			<button
				type="button"
				disabled={isDisabled}
				aria-label="Mở khóa số điện thoại"
				title={isDisabled ? "Không thể mở khóa" : "Click để mở khóa SĐT"}
				onClick={handlePillClick}
				className="inline-flex disabled:cursor-not-allowed"
			>
				{pillContent}
			</button>
		</SmartUnlockPopover>
	);
};
