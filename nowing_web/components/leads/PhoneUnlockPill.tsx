"use client";

import { useAtom, useAtomValue } from "jotai";
import { Check, Phone } from "lucide-react";
import { motion } from "motion/react";
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
const FLIP_DURATION_MS = 150;
const FLIP_CLASS_HOLD_MS = 600;

export interface PhoneUnlockPillProps {
	lead: Lead;
	workspaceId: number | string;
	className?: string;
	showIcon?: boolean;
	onUnlock?: (unlocked: boolean) => void;
	onPhoneChange?: (leadId: string, phone: string | null, unlocked: boolean) => void;
}

function isValidPhoneString(value?: string | null) {
	const safe = (value || "").trim();
	if (!safe) return false;
	if (safe.includes("|") || /website/i.test(safe)) return false;
	if (safe.includes("*")) return true;
	const digits = safe.replace(/\D/g, "");
	return digits.length >= 9;
}

export const PhoneUnlockPill: React.FC<PhoneUnlockPillProps> = ({
	lead,
	workspaceId,
	className,
	showIcon = true,
	onUnlock,
	onPhoneChange,
}) => {
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const fastUnlockKey = makeFastUnlockKey(workspaceId, currentUser?.id);
	const [fastUnlockSession, setFastUnlockSession] = useAtom(fastUnlockSessionAtom(fastUnlockKey));

	const [isUnlocked, setIsUnlocked] = useState(lead.is_unlocked);
	const [displayPhone, setDisplayPhone] = useState(lead.phone ?? "");
	const [copied, setCopied] = useState(false);
	const [isOpen, setIsOpen] = useState(false);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const [isRelocking, setIsRelocking] = useState(false);
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

	const isFastUnlockActive = !!fastUnlockSession && fastUnlockSession.expires_at > Date.now();

	const safePhone = (displayPhone || "").trim();
	const isMasked = safePhone.includes("*");
	const isPhoneValid = isValidPhoneString(safePhone);

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
			setFastUnlockSession(null);
			return;
		}
		setFastUnlockSession({ expires_at: Date.now() + FAST_UNLOCK_TTL_MS });
	};

	const performUnlock = async () => {
		if (!contactId || isUnlocking) return;
		setIsUnlocking(true);

		// Extend/reset the fast-unlock TTL on every unlock action.
		if (isFastUnlockActive || fastUnlockEnabled) {
			applyFastUnlockSession(true);
		}

		try {
			const res = await leadsApiService.unlockContact(workspaceId, lead.id, contactId);
			const newPhone = typeof res.phone === "string" ? res.phone : "";

			if (!res.is_unlocked || !isValidPhoneString(newPhone)) {
				toast.error("Không thể mở khóa SĐT");
				setIsUnlocking(false);
				setIsOpen(false);
				return;
			}

			setIsUnlocked(true);
			setDisplayPhone(newPhone);
			onUnlock?.(true);
			onPhoneChange?.(lead.id, newPhone, true);
			setIsFlipped(true);
			setTimeout(() => setIsFlipped(false), FLIP_CLASS_HOLD_MS);

			toast.success(`Đã mở khóa SĐT -${UNLOCK_COST_CREDITS} credits`, {
				duration: 5000,
				action: (
					<button
						type="button"
						data-testid="relock-undo-button"
						onClick={() => {
							if (isRelocking) return;
							void performRelock();
						}}
						className="ml-2 text-xs underline"
					>
						Hoàn tác
					</button>
				),
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
		if (!contactId || isRelocking) return;
		setIsRelocking(true);
		try {
			const res = await leadsApiService.relockContact(workspaceId, lead.id, contactId);
			const maskedPhone = res.phone ?? lead.phone ?? "";
			setIsUnlocked(false);
			onUnlock?.(false);
			setDisplayPhone(maskedPhone);
			// Report null phone to parent so it falls back to the masked lead.phone
			onPhoneChange?.(lead.id, null, false);
			toast.success("Đã hoàn tác mở khóa - +1.5 credits");
		} catch (err) {
			const message = err instanceof Error ? err.message : "Không thể hoàn tác";
			toast.error(message);
		} finally {
			setIsRelocking(false);
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

		setFastUnlockEnabled(false);
		setIsOpen(true);
	};

	const handleConfirm = () => {
		applyFastUnlockSession(fastUnlockEnabled);
		void performUnlock();
	};

	const pillContent = (
		<motion.span
			animate={
				isFlipped
					? { rotateX: [0, 90, 0], scale: [1, 1.05, 1], opacity: [1, 0.8, 1] }
					: { rotateX: 0, scale: 1, opacity: 1 }
			}
			transition={{ duration: FLIP_DURATION_MS / 1000 }}
			style={{ transformOrigin: "center center" }}
			className={cn(
				"inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-xs font-mono font-medium cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50",
				copied
					? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-xs"
					: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/40",
				isDisabled && "opacity-50 cursor-not-allowed",
				isFlipped && "animate-flip",
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
		</motion.span>
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
			isLoading={isUnlocking}
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
