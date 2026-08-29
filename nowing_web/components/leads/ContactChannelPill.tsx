"use client";

import { Check, Mail, MessageCircle, User } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { Lead } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn, copyToClipboard } from "@/lib/utils";
import { SmartUnlockPopover } from "./SmartUnlockPopover";

const UNLOCK_COST_CREDITS = 1.5;

const CHANNEL_META: Record<
	string,
	{ label: string; icon: React.ElementType; colorClass: string; isLink?: boolean }
> = {
	email: {
		label: "Email",
		icon: Mail,
		colorClass: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
	},
	zalo: {
		label: "Zalo",
		icon: MessageCircle,
		colorClass: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20",
		isLink: true,
	},
	facebook: {
		label: "Facebook",
		icon: MessageCircle,
		colorClass: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20",
		isLink: true,
	},
	telegram: {
		label: "Telegram",
		icon: MessageCircle,
		colorClass: "bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/20",
		isLink: true,
	},
	username: {
		label: "Username",
		icon: User,
		colorClass: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20",
	},
};

function getMeta(channel: string) {
	return (
		CHANNEL_META[channel] ?? {
			label: channel.charAt(0).toUpperCase() + channel.slice(1),
			icon: MessageCircle,
			colorClass: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-400 border-zinc-500/20",
		}
	);
}

export interface ContactChannelPillProps {
	lead: Lead;
	workspaceId: number | string;
	channel: string;
	value: string;
	className?: string;
	onChange?: (leadId: string, channel: string, value: string | null, unlocked: boolean) => void;
}

export const ContactChannelPill: React.FC<ContactChannelPillProps> = ({
	lead,
	workspaceId,
	channel,
	value,
	className,
	onChange,
}) => {
	const contactId = lead.contact_id;
	const isDnc = lead.consent_status === "withdrawn";
	const isInvalid = lead.is_valid === false;
	const isDisabled = !contactId || isDnc || isInvalid;

	const initiallyUnlocked = lead.unlocked_channels?.includes(channel) ?? false;
	const [isUnlocked, setIsUnlocked] = useState(initiallyUnlocked);
	const [displayValue, setDisplayValue] = useState(value);
	const [copied, setCopied] = useState(false);
	const [isOpen, setIsOpen] = useState(false);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		setIsUnlocked(lead.unlocked_channels?.includes(channel) ?? false);
		setDisplayValue(value);
	}, [lead.unlocked_channels, channel, value]);

	useEffect(() => {
		return () => {
			if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
		};
	}, []);

	const meta = getMeta(channel);
	const Icon = meta.icon;
	const isMasked = (displayValue || "").includes("*");

	const handleCopy = async (e: React.MouseEvent | React.KeyboardEvent) => {
		e.stopPropagation();
		e.preventDefault();
		if (copied || isMasked || !displayValue) return;

		const success = await copyToClipboard(displayValue);
		if (success) {
			setCopied(true);
			toast.success(`Đã copy ${meta.label} ${displayValue}!`, { duration: 1500 });
			if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
			copyTimerRef.current = setTimeout(() => setCopied(false), 1500);
		} else {
			toast.error(`Không thể copy ${meta.label}`);
		}
	};

	const performUnlock = async () => {
		if (!contactId || isUnlocking) return;
		setIsUnlocking(true);

		try {
			const res = await leadsApiService.unlockContact(workspaceId, lead.id, contactId, channel);

			const resolved =
				(channel === "email" ? res.email : null) ??
				(channel === "phone" ? res.phone : null) ??
				res.external_chat_ids?.[channel] ??
				displayValue;

			if (!res.is_unlocked || !resolved || resolved.includes("*")) {
				toast.error(`Không thể mở khóa ${meta.label}`);
				setIsUnlocking(false);
				setIsOpen(false);
				return;
			}

			setIsUnlocked(true);
			setDisplayValue(resolved);
			onChange?.(lead.id, channel, resolved, true);

			toast.success(`Đã mở khóa ${meta.label} -${UNLOCK_COST_CREDITS} credits`, {
				duration: 5000,
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : "Không thể mở khóa";
			toast.error(message);
		} finally {
			setIsUnlocking(false);
			setIsOpen(false);
		}
	};

	const handlePillClick = (e: React.MouseEvent) => {
		e.stopPropagation();
		if (isDisabled) return;

		if (isUnlocked) {
			if (meta.isLink) {
				window.open(displayValue, "_blank", "noopener,noreferrer");
				return;
			}
			void handleCopy(e);
			return;
		}

		setIsOpen(true);
	};

	if (!value) return null;

	const pillContent = (
		<span
			className={cn(
				"inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-xs font-mono font-medium cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all duration-150",
				meta.colorClass,
				isDisabled && "opacity-50 cursor-not-allowed",
				className
			)}
			data-testid={`contact-pill-${channel}`}
		>
			{copied ? (
				<Check
					className="size-3.5 text-emerald-600 dark:text-emerald-400 animate-in zoom-in-50"
					aria-hidden="true"
				/>
			) : (
				<Icon className="size-3.5" aria-hidden="true" />
			)}
			<span className="truncate max-w-[160px]">{displayValue}</span>
		</span>
	);

	if (isUnlocked) {
		return (
			<button
				type="button"
				aria-label={`Copy ${meta.label} ${displayValue}`}
				title={copied ? "Đã copy" : `Click để ${meta.isLink ? "mở" : "copy"}: ${displayValue}`}
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
			maskedValue={displayValue}
			costCredits={UNLOCK_COST_CREDITS}
			fastUnlockEnabled={false}
			onToggleFastUnlock={() => {}}
			onConfirm={performUnlock}
			onCancel={() => setIsOpen(false)}
			isLoading={isUnlocking}
			title={`Xác nhận mở khóa ${meta.label}`}
			actionLabel={`Mở khóa ${meta.label}`}
		>
			<button
				type="button"
				disabled={isDisabled}
				aria-label={`Mở khóa ${meta.label}`}
				title={isDisabled ? "Không thể mở khóa" : `Click để mở khóa ${meta.label}`}
				onClick={handlePillClick}
				className="inline-flex disabled:cursor-not-allowed"
			>
				{pillContent}
			</button>
		</SmartUnlockPopover>
	);
};
