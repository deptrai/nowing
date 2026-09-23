"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { buildBackendUrl } from "@/lib/env-config";

// Story 37.5 / AC-4: prospect self-serve opt-out ("Yêu cầu xóa thông tin")
// per Decree 13/2023/NĐ-CP.  One confirm click POSTs to the public endpoint;
// the lead UUID in the URL is the capability so no login is required.

interface PitchOptOutFormProps {
	workspaceRef: string;
	leadId: string;
	companyName?: string | null;
}

export function PitchOptOutForm({ workspaceRef, leadId, companyName }: PitchOptOutFormProps) {
	const [state, setState] = useState<"idle" | "submitting" | "done" | "error">("idle");

	const submit = async () => {
		if (state === "submitting" || state === "done") return;
		setState("submitting");
		try {
			const res = await fetch(
				buildBackendUrl(
					`/api/v1/public/pitch/${encodeURIComponent(workspaceRef)}/${encodeURIComponent(leadId)}/opt-out`
				),
				{ method: "POST" }
			);
			// The endpoint always answers {"status":"ok"} for well-formed calls —
			// treat any 2xx as a recorded request; anything else shows retry.
			setState(res.ok ? "done" : "error");
		} catch {
			setState("error");
		}
	};

	if (state === "done") {
		return (
			<div className="space-y-2 text-center">
				<p className="font-medium">Yêu cầu đã được ghi nhận.</p>
				<p className="text-sm text-muted-foreground">
					Thông tin liên hệ của {companyName || "doanh nghiệp bạn"} đã được xóa khỏi hệ thống và sẽ
					không còn được liên hệ nữa, theo Nghị định 13/2023/NĐ-CP.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4 text-center">
			<p className="text-sm text-muted-foreground">
				Xác nhận xóa toàn bộ thông tin liên hệ của{" "}
				<span className="font-medium text-foreground">{companyName || "doanh nghiệp của bạn"}</span>{" "}
				khỏi hệ thống outreach. Hành động này đồng thời dừng mọi chiến dịch đang gửi tới bạn.
			</p>
			<Button
				onClick={submit}
				disabled={state === "submitting"}
				variant="destructive"
				size="lg"
				className="w-full sm:w-auto"
			>
				{state === "submitting" ? "Đang xử lý…" : "Xác nhận xóa thông tin"}
			</Button>
			{state === "error" ? (
				<p className="text-xs text-destructive">
					Có lỗi xảy ra — vui lòng thử lại hoặc liên hệ trực tiếp bên gửi.
				</p>
			) : null}
		</div>
	);
}
