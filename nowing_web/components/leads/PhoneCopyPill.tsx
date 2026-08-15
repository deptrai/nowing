"use client";

import { Check, Phone } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn, copyToClipboard } from "@/lib/utils";

export interface PhoneCopyPillProps {
	phone: string;
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

	// Normalize phone for clipboard (digits and + only)
	const safePhone = phone || "";
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
			onClick={handleCopy}
			className={cn(
				"inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium transition-all duration-200 cursor-pointer select-none focus:outline-none focus:ring-2 focus:ring-emerald-500/50",
				copied
					? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm"
					: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 hover:border-emerald-500/30",
				className
			)}
		>
			{showIcon && (
				<span className="shrink-0 transition-transform duration-200">
					{copied ? (
						<Check className="w-3.5 h-3.5 text-emerald-400 animate-in zoom-in-50" />
					) : (
						<Phone className="w-3.5 h-3.5 text-emerald-400" />
					)}
				</span>
			)}
			<span>{safePhone}</span>
			<span className="text-[10px] text-emerald-400/70 font-sans ml-0.5">
				{copied ? "(Đã copy)" : "(Click to Copy)"}
			</span>
		</button>
	);
};
