"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { VisualCadenceBuilder } from "@/components/automations/VisualCadenceBuilder";
import type { SequenceCreate } from "@/contracts/types/sequence.types";
import { sequenceApiService } from "@/lib/apis/sequence-api.service";

export default function NewCampaignPage() {
	const params = useParams();
	const router = useRouter();
	const workspaceId = Number(params?.workspace_id);

	const [isSaving, setIsSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSave = async (payload: SequenceCreate) => {
		if (Number.isNaN(workspaceId)) {
			setError("Workspace ID không hợp lệ.");
			return;
		}
		setIsSaving(true);
		setError(null);
		try {
			const res = await sequenceApiService.createSequence(workspaceId, payload);
			router.push(`/dashboard/${workspaceId}/automations/campaigns/${res.id}`);
		} catch (err: unknown) {
			console.error("Failed to create sequence:", err);
			const message =
				err instanceof Error
					? err.message
					: "Không thể tạo chiến dịch. Vui lòng kiểm tra lại cấu hình.";
			setError(message);
		} finally {
			setIsSaving(false);
		}
	};

	if (Number.isNaN(workspaceId)) {
		return (
			<div className="p-6 max-w-5xl mx-auto text-sm text-destructive">
				Workspace ID không hợp lệ.
			</div>
		);
	}

	return (
		<div className="p-6 space-y-6 max-w-5xl mx-auto">
			<div className="flex items-center gap-3">
				<Link
					href={`/dashboard/${workspaceId}/automations/campaigns`}
					className="p-2 border rounded-lg hover:bg-accent text-muted-foreground transition-colors"
				>
					<ArrowLeft className="w-4 h-4" />
				</Link>
				<div>
					<h1 className="text-xl font-bold text-foreground">Thiết lập chiến dịch Outreach mới</h1>
					<p className="text-xs text-muted-foreground">
						Tạo chuỗi quy trình nuôi dưỡng tự động đa bước
					</p>
				</div>
			</div>

			{error && (
				<div className="p-4 bg-destructive/10 border border-destructive/20 text-destructive text-sm rounded-xl">
					{error}
				</div>
			)}

			<VisualCadenceBuilder workspaceId={workspaceId} onSave={handleSave} isSaving={isSaving} />
		</div>
	);
}
