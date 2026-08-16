"use client";

import { Check, Phone } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn, copyToClipboard } from "@/lib/utils";

export interface PhoneCopyPillProps {
	phone?: string | null;
	className?: string;
	showIcon?: boolean;
}

export const PhoneCopyPill: React.FC<PhoneCopyPillProps> = ({
	phone,
	className,
	showIcon = true,
}) => {
	const [copied, setCopied] = useState(false);
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		return () => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
			}
		};
	}, []);

	const safePhone = (phone || "").trim();
	// Check if valid phone (digits with length >= 8 and no pipes or headers)
	const isPhoneValid =
		Boolean(safePhone) &&
		!safePhone.includes("|") &&
		!safePhone.includes("Website") &&
		safePhone.replace(/\D/g, "").length >= 8;

	if (!isPhoneValid) {
		return <span className="text-muted-foreground/40 text-[11px] select-none">—</span>;
	}

	const normalizedPhone = safePhone.replace(/[^\d+]/g, "");

	const handleCopy = async (e: React.MouseEvent | React.KeyboardEvent) => {
		e.stopPropagation();
		e.preventDefault();

		if (copied) return;

		const success = await copyToClipboard(normalizedPhone || safePhone);
		if (success) {
			setCopied(true);
			toast.success(`Đã copy SĐT ${safePhone}!`, {
				duration: 1500,
			});

			if (timerRef.current) {
				clearTimeout(timerRef.current);
			}
			timerRef.current = setTimeout(() => {
				setCopied(false);
			}, 1500);
		} else {
			toast.error("Không thể copy số điện thoại");
		}
	};

	return (
		<button
			type="button"
			aria-label={`Copy phone number ${safePhone}`}
			title={copied ? "Đã copy vào bộ nhớ tạm" : `Click để copy: ${safePhone}`}
			onClick={handleCopy}
			className={cn(
				"inline-flex items-center gap-1.5 h-6 px-2 rounded-md text-[11px] font-mono font-medium transition-all duration-150 cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-emerald-500/50",
				copied
					? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 shadow-xs"
					: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/40",
				className
			)}
		>
			{showIcon && (
				<span className="shrink-0">
					{copied ? (
						<Check className="size-3 text-emerald-600 dark:text-emerald-400 animate-in zoom-in-50" />
					) : (
						<Phone className="size-3 text-emerald-600 dark:text-emerald-400" />
					)}
				</span>
			)}
			<span className="tabular-nums tracking-tight">{safePhone}</span>
			{copied && (
				<span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-sans ml-0.5">
					✓
				</span>
			)}
		</button>
	);
};
