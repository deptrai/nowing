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
	unlockedPhones?: Record<string, string | null>;
	onPhoneChange?: (leadId: string, phone: string | null, unlocked: boolean) => void;
}

export const FloatingBulkActionBar: React.FC<FloatingBulkActionBarProps> = ({
	selectedCount,
	selectedLeads = [],
	workspaceId = "1",
	onExportLarkBase,
	onBulkZalo,
	onClearSelection,
	className,
	unlockedPhones = {},
	onPhoneChange,
}) => {
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const fastUnlockKey = makeFastUnlockKey(workspaceId, currentUser?.id);
	const [fastUnlockSession, setFastUnlockSession] = useAtom(fastUnlockSessionAtom(fastUnlockKey));

	const [isOpen, setIsOpen] = useState(false);
	const [isUnlocking, setIsUnlocking] = useState(false);
	const [fastUnlockEnabled, setFastUnlockEnabled] = useState(false);

	const isFastUnlockActive = !!fastUnlockSession && fastUnlockSession.expires_at > Date.now();

	const unlockedCount = useMemo(
		() => selectedLeads.filter((l) => l.is_unlocked || Boolean(unlockedPhones[l.id])).length,
		[selectedLeads, unlockedPhones]
	);

	const ineligibleLeads = useMemo(
		() =>
			selectedLeads.filter(
				(l) =>
					!l.contact_id ||
					l.consent_status === "withdrawn" ||
					l.is_valid === false ||
					l.is_unlocked ||
					Boolean(unlockedPhones[l.id])
			),
		[selectedLeads, unlockedPhones]
	);

	const eligibleLeads = useMemo(
		() =>
			selectedLeads.filter(
				(l) =>
					l.contact_id &&
					l.consent_status !== "withdrawn" &&
					l.is_valid !== false &&
					!l.is_unlocked &&
					!unlockedPhones[l.id]
			),
		[selectedLeads, unlockedPhones]
	);

	const allSelectedEligible = eligibleLeads.length === selectedCount && selectedCount > 0;
	const previewPhone = eligibleLeads[0]?.phone ?? "SĐT";
	const totalCost = selectedCount * UNLOCK_COST_CREDITS;

	if (selectedCount < 2) {
		return null;
	}

	const applyFastUnlockSession = (enabled: boolean) => {
		if (!enabled) {
			setFastUnlockSession(null);
			return;
		}
		setFastUnlockSession({ expires_at: Date.now() + FAST_UNLOCK_TTL_MS });
	};

	const performBulkUnlock = async () => {
		if (eligibleLeads.length === 0 || isUnlocking) return;
		if (!allSelectedEligible) {
			toast.warning("Một số lead đã chọn không đủ điều kiện mở khóa.");
			return;
		}
		setIsUnlocking(true);

		// Reset TTL on every bulk unlock action.
		if (isFastUnlockActive || fastUnlockEnabled) {
			applyFastUnlockSession(true);
		}

		let success = 0;
		let failed = 0;
		for (const lead of eligibleLeads) {
			if (!lead.contact_id) continue;
			try {
				const res = await leadsApiService.unlockContact(
					workspaceId,
					lead.id,
					lead.contact_id,
					"phone"
				);
				if (res.is_unlocked && typeof res.phone === "string") {
					onPhoneChange?.(lead.id, res.phone, true);
					success++;
				} else {
					failed++;
				}
			} catch (err) {
				failed++;
				console.error("Bulk unlock failed for lead", lead.id, err);
			}
		}

		setIsUnlocking(false);
		setIsOpen(false);

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
		if (ineligibleLeads.length > 0) {
			toast.warning("Có lead đã chọn không hợp lệ hoặc đã được mở khóa.");
			return;
		}
		if (eligibleLeads.length === 0) {
			toast.warning("Không có SĐT hợp lệ trong các leads đã chọn.");
			return;
		}
		// Pre-seed the popover toggle from the active session.
		setFastUnlockEnabled(isFastUnlockActive);
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
					<CheckSquare className="h-3.5 w-3.5" aria-hidden="true" />
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
				<SmartUnlockPopover
					open={isOpen}
					onOpenChange={setIsOpen}
					maskedValue={previewPhone}
					costCredits={totalCost}
					fastUnlockEnabled={fastUnlockEnabled}
					onToggleFastUnlock={setFastUnlockEnabled}
					onConfirm={performBulkUnlock}
					onCancel={() => setIsOpen(false)}
					isBulk
					selectedCount={selectedCount}
					isLoading={isUnlocking}
				>
					<Button
						type="button"
						onClick={handlePillClick}
						size="sm"
						data-testid="bulk-unlock-button"
						disabled={!allSelectedEligible}
						title={
							allSelectedEligible
								? "Mở khóa SĐT các lead đã chọn"
								: "Có lead không hợp lệ hoặc đã mở khóa"
						}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors shadow-sm shadow-emerald-950/20 disabled:opacity-50 disabled:cursor-not-allowed"
					>
						<PhoneCall className="w-3.5 h-3.5" aria-hidden="true" />
						Mở khóa SĐT hàng loạt ({eligibleLeads.length - unlockedCount})
					</Button>
				</SmartUnlockPopover>

				{onExportLarkBase && (
					<button
						type="button"
						onClick={onExportLarkBase}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-muted hover:bg-muted/80 text-foreground border border-border transition-colors cursor-pointer"
					>
						<Download
							className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400"
							aria-hidden="true"
						/>
						Xuất Lark Base
					</button>
				)}

				{onBulkZalo && (
					<button
						type="button"
						onClick={onBulkZalo}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer shadow-sm"
					>
						<MessageSquare className="w-3.5 h-3.5" aria-hidden="true" />
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
				<X className="w-4 h-4" aria-hidden="true" />
			</button>
		</aside>
	);
};
