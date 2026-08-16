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
			setMonthlySpendCap("");
			setLeadCapacity("50");
			setIsAcceptingLeads(true);
		}
	}, [member]);

	const handleSave = async () => {
		if (!member) return;

		const capMicros = monthlySpendCap.trim() === "" ? null : Number(monthlySpendCap) * 1_000_000;
		const capacity = Number(leadCapacity);

		if (Number.isNaN(capacity) || capacity < 0) {
			toast.error("Lead capacity phải là số dương");
			return;
		}

		if (
			monthlySpendCap.trim() !== "" &&
			(capMicros === null || Number.isNaN(capMicros) || capMicros < 0)
		) {
			toast.error("Monthly spend cap phải là số dương");
			return;
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
			toast.error("Cập nhật thất bại");
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
						{saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Lưu"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
