"use client";

import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface SmartUnlockPopoverProps {
	children: React.ReactNode;
	maskedPhone: string;
	costCredits: number;
	fastUnlockEnabled: boolean;
	onToggleFastUnlock: (enabled: boolean) => void;
	onConfirm: () => void;
	onCancel: () => void;
	isBulk?: boolean;
	selectedCount?: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	className?: string;
}

export function SmartUnlockPopover({
	children,
	maskedPhone,
	costCredits,
	fastUnlockEnabled,
	onToggleFastUnlock,
	onConfirm,
	onCancel,
	isBulk = false,
	selectedCount = 1,
	open,
	onOpenChange,
	className,
}: SmartUnlockPopoverProps) {
	const checkboxId = useId();

	const actionLabel = isBulk ? `Mở khóa SĐT hàng loạt` : `Mở khóa SĐT`;
	const displayCost = costCredits % 1 === 0 ? costCredits.toString() : costCredits.toFixed(1);

	return (
		<Popover open={open} onOpenChange={onOpenChange}>
			<PopoverTrigger asChild className={className}>
				{children}
			</PopoverTrigger>
			<PopoverContent
				data-testid="smart-unlock-popover"
				className="w-80 space-y-4 p-4"
				align="start"
				sideOffset={6}
			>
				<div className="space-y-1">
					<p className="text-sm font-medium text-foreground">Xác nhận mở khóa SĐT</p>
					<p
						className="font-mono text-2xl font-semibold tracking-tight text-emerald-600 dark:text-emerald-400"
						data-testid="smart-unlock-phone-preview"
					>
						{maskedPhone}
					</p>
					<p className="text-sm text-muted-foreground">
						{isBulk ? `${selectedCount} SĐT · ` : ""}
						{displayCost} credits
					</p>
				</div>

				<div className="flex items-start gap-2 rounded-md border border-border/80 bg-muted/40 p-3">
					<Checkbox
						id={checkboxId}
						checked={fastUnlockEnabled}
						onCheckedChange={(checked) => onToggleFastUnlock(Boolean(checked))}
					/>
					<div className="grid gap-0.5">
						<label htmlFor={checkboxId} className="cursor-pointer text-sm font-medium leading-none">
							1-Click Fast Unlock cho phiên này
						</label>
						<p className="text-xs text-muted-foreground">
							Bỏ qua hộp thoại xác nhận trong 30 phút tới.
						</p>
					</div>
				</div>

				<div className="flex items-center justify-end gap-2">
					<Button variant="outline" size="sm" onClick={onCancel} type="button">
						Hủy
					</Button>
					<Button
						size="sm"
						onClick={onConfirm}
						type="button"
						className="bg-emerald-600 text-white hover:bg-emerald-700"
					>
						{actionLabel}
					</Button>
				</div>
			</PopoverContent>
		</Popover>
	);
}
