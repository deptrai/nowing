"use client";

import { useAtom, useAtomValue } from "jotai";
import { CheckSquare, Download, MessageSquare, PhoneCall, X } from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { fastUnlockSessionAtom, makeFastUnlockKey } from "@/atoms/leads/leads-canvas.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import type { Lead } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn } from "@/lib/utils";
import { SmartUnlockPopover } from "./SmartUnlockPopover";

const FAST_UNLOCK_TTL_MS = 30 * 60 * 1000;
const UNLOCK_COST_CREDITS = 1.5;

export interface FloatingBulkActionBarProps {
	selectedCount: number;
	selectedLeads?: Lead[];
	workspaceId?: number | string;
	onExportLarkBase?: () => void;
	onBulkZalo?: () => void;
	onClearSelection: () => void;
	className?: string;
}

export const FloatingBulkActionBar: React.FC<FloatingBulkActionBarProps> = ({
	selectedCount,
	selectedLeads = [],
	workspaceId = "1",
	onExportLarkBase,
	onBulkZalo,
	onClearSelection,
	className,
}) => {
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const [, setFastUnlockSessions] = useAtom(fastUnlockSessionAtom);

	const [isOpen, setIsOpen] = useState(false);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const [fastUnlockEnabled, setFastUnlockEnabled] = useState(false);

	const unlockedCount = useMemo(
		() => selectedLeads.filter((l) => l.is_unlocked).length,
		[selectedLeads]
	);

	const eligibleLeads = useMemo(
		() =>
			selectedLeads.filter(
				(l) => l.contact_id && l.consent_status !== "withdrawn" && l.is_valid !== false
			),
		[selectedLeads]
	);

	const previewPhone = eligibleLeads[0]?.phone ?? "SĐT";
	const totalCost = eligibleLeads.length * UNLOCK_COST_CREDITS;

	if (selectedCount < 2) {
		return null;
	}

	const applyFastUnlockSession = (enabled: boolean) => {
		const fastUnlockKey = makeFastUnlockKey(workspaceId, currentUser?.id);
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

	const performBulkUnlock = async () => {
		if (eligibleLeads.length === 0 || isUnlocking) return;
		setIsUnlocking(true);

		let success = 0;
		let failed = 0;
		for (const lead of eligibleLeads) {
			if (!lead.contact_id) continue;
			try {
				await leadsApiService.unlockContact(workspaceId, lead.id, lead.contact_id);
				success++;
			} catch (err) {
				failed++;
				console.error("Bulk unlock failed for lead", lead.id, err);
			}
		}

		setIsUnlocking(false);
		setIsOpen(false);
		applyFastUnlockSession(fastUnlockEnabled);

		if (success > 0) {
			toast.success(
				`Đã mở khóa ${success} SĐT -${(success * UNLOCK_COST_CREDITS).toFixed(1)} credits`
			);
		}
		if (failed > 0) {
			toast.error(`${failed} SĐT không mở khóa được do lỗi server hoặc hết credits.`);
		}
	};

	const handlePillClick = () => {
		if (eligibleLeads.length === 0) {
			toast.warning("Không có SĐT hợp lệ trong các leads đã chọn.");
			return;
		}
		const _fastUnlockKey = makeFastUnlockKey(workspaceId, currentUser?.id);
		// State will be derived on next render; for the popover we seed it from session
		setFastUnlockEnabled(false); // default false, user can toggle
		setIsOpen(true);
	};

	return (
		<aside
			aria-label="Thao tác hàng loạt"
			data-testid="floating-bulk-action-bar"
			className={cn(
				"fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3 px-4 py-2.5",
				"rounded-2xl border border-border bg-card/95 text-foreground shadow-2xl backdrop-blur-md",
				"animate-in fade-in slide-in-from-bottom-4 duration-200",
				className
			)}
		>
			<div className="flex items-center gap-2 pr-3 border-r border-border">
				<span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400">
					<CheckSquare className="h-3.5 w-3.5" />
				</span>
				<span className="text-xs font-semibold text-foreground">
					Đã chọn{" "}
					<span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">
						{selectedCount}
					</span>{" "}
					leads
				</span>
			</div>

			<div className="flex items-center gap-1.5">
				{eligibleLeads.length > 0 && (
					<SmartUnlockPopover
						open={isOpen}
						onOpenChange={setIsOpen}
						maskedPhone={previewPhone}
						costCredits={totalCost}
						fastUnlockEnabled={fastUnlockEnabled}
						onToggleFastUnlock={setFastUnlockEnabled}
						onConfirm={performBulkUnlock}
						onCancel={() => setIsOpen(false)}
						isBulk
						selectedCount={eligibleLeads.length}
					>
						<Button
							type="button"
							onClick={handlePillClick}
							size="sm"
							data-testid="bulk-unlock-button"
							className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors shadow-sm shadow-emerald-950/20"
						>
							<PhoneCall className="w-3.5 h-3.5" />
							Mở khóa SĐT ({eligibleLeads.length - unlockedCount})
						</Button>
					</SmartUnlockPopover>
				)}

				{onExportLarkBase && (
					<button
						type="button"
						onClick={onExportLarkBase}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-muted hover:bg-muted/80 text-foreground border border-border transition-colors cursor-pointer"
					>
						<Download className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
						Xuất Lark Base
					</button>
				)}

				{onBulkZalo && (
					<button
						type="button"
						onClick={onBulkZalo}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer shadow-sm"
					>
						<MessageSquare className="w-3.5 h-3.5" />
						Gửi Zalo hàng loạt
					</button>
				)}
			</div>

			<button
				type="button"
				onClick={onClearSelection}
				title="Bỏ chọn tất cả"
				className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer ml-1"
			>
				<X className="w-4 h-4" />
			</button>
		</aside>
	);
};
