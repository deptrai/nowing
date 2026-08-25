"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { Membership } from "@/contracts/types/members.types";
import { leadPipelineApiService } from "@/lib/apis/lead-pipeline-api.service";

export interface MemberSpendCapDialogProps {
	member: Membership | null;
	workspaceId: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function MemberSpendCapDialog({
	member,
	workspaceId,
	open,
	onOpenChange,
}: MemberSpendCapDialogProps) {
	const [monthlySpendCap, setMonthlySpendCap] = useState<string>("");
	const [leadCapacity, setLeadCapacity] = useState<string>("50");
	const [isAcceptingLeads, setIsAcceptingLeads] = useState(true);
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		if (member) {
			setMonthlySpendCap(
				member.monthly_spend_cap_micros ? String(member.monthly_spend_cap_micros / 1_000_000) : ""
			);
			setLeadCapacity(String(member.lead_capacity ?? 50));
			setIsAcceptingLeads(member.is_accepting_leads ?? true);
		}
	}, [member]);

	const handleSave = async () => {
		if (!member) return;

		const capInput = monthlySpendCap.trim();
		let capMicros: number | null = null;
		const capacity = Number(leadCapacity);

		if (Number.isNaN(capacity) || !Number.isInteger(capacity) || capacity < 0) {
			toast.error("Lead capacity phải là số nguyên dương");
			return;
		}

		if (capInput !== "") {
			const capNumber = Number(capInput);
			if (Number.isNaN(capNumber) || !Number.isInteger(capNumber) || capNumber < 0) {
				toast.error("Monthly spend cap phải là số nguyên dương (USD)");
				return;
			}
			capMicros = capNumber * 1_000_000;
			if (Number.isNaN(capMicros)) {
				toast.error("Monthly spend cap không hợp lệ");
				return;
			}
		}

		try {
			setSaving(true);
			await Promise.all([
				leadPipelineApiService.updateMemberSpendCap(workspaceId, member.user_id, capMicros),
				leadPipelineApiService.updateMemberLeadCapacity(
					workspaceId,
					member.user_id,
					isAcceptingLeads,
					capacity
				),
			]);
			toast.success("Đã cập nhật hạn mức và sức chứa lead");
			onOpenChange(false);
		} catch (err) {
			const apiErr = err as {
				data?: { detail?: string };
				response?: { data?: { detail?: string } };
				message?: string;
			};
			const message =
				apiErr?.data?.detail ??
				apiErr?.response?.data?.detail ??
				apiErr?.message ??
				"Cập nhật thất bại";
			toast.error(message);
			console.error("Failed to update member spend cap", err);
		} finally {
			setSaving(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[420px]">
				<DialogHeader>
					<DialogTitle>Spend Cap &amp; Lead Capacity</DialogTitle>
					<DialogDescription>
						Cấu hình hạn mức chi tiêu hàng tháng và sức chứa lead cho{" "}
						<span className="font-medium text-foreground">
							{member?.user_display_name ?? member?.user_email ?? "thành viên"}
						</span>
						.
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4 py-2">
					<div className="space-y-1.5">
						<Label htmlFor="spend-cap">Monthly spend cap (USD)</Label>
						<Input
							id="spend-cap"
							type="number"
							min={0}
							placeholder="Không giới hạn"
							value={monthlySpendCap}
							onChange={(e) => setMonthlySpendCap(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">
							Để trống nếu không muốn giới hạn. Giá trị USD, sẽ chuyển thành micros.
						</p>
					</div>

					<div className="space-y-1.5">
						<Label htmlFor="lead-capacity">Lead capacity</Label>
						<Input
							id="lead-capacity"
							type="number"
							min={0}
							value={leadCapacity}
							onChange={(e) => setLeadCapacity(e.target.value)}
						/>
					</div>

					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="accepting-leads">Nhận lead tự động</Label>
							<p className="text-xs text-muted-foreground">Bật để nhận lead qua Round-Robin.</p>
						</div>
						<Switch
							id="accepting-leads"
							checked={isAcceptingLeads}
							onCheckedChange={setIsAcceptingLeads}
							aria-label="Nhận lead tự động"
						/>
					</div>
				</div>

				<DialogFooter>
					<Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
						Hủy
					</Button>
					<Button type="button" onClick={handleSave} disabled={saving}>
						{saving ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : "Lưu"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
