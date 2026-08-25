"use client";

import { BarChart3, Clock, Pause, Play, Plus, RefreshCw, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { Sequence } from "@/contracts/types/sequence.types";
import { sequenceApiService } from "@/lib/apis/sequence-api.service";

export default function CampaignsListPage() {
	const params = useParams();
	const workspaceId = Number(params?.workspace_id);

	const [sequences, setSequences] = useState<Sequence[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchSequences = useCallback(async () => {
		if (Number.isNaN(workspaceId)) return;
		setLoading(true);
		try {
			const data = await sequenceApiService.listSequences(workspaceId);
			setSequences(data);
		} catch (err) {
			console.error("Failed to load sequences:", err);
		} finally {
			setLoading(false);
		}
	}, [workspaceId]);

	useEffect(() => {
		fetchSequences();
	}, [fetchSequences]);

	const toggleStatus = async (sequence: Sequence) => {
		if (Number.isNaN(workspaceId)) return;
		try {
			if (sequence.status === "active") {
				await sequenceApiService.pauseSequence(workspaceId, sequence.id);
			} else {
				await sequenceApiService.resumeSequence(workspaceId, sequence.id);
			}
			await fetchSequences();
		} catch (err) {
			console.error("Failed to toggle sequence status:", err);
		}
	};

	if (Number.isNaN(workspaceId)) {
		return (
			<div className="p-6 max-w-6xl mx-auto text-sm text-destructive">
				Workspace ID không hợp lệ.
			</div>
		);
	}

	return (
		<div className="p-6 space-y-6 max-w-6xl mx-auto">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold text-foreground">
						Chiến dịch tiếp cận tự động (Drip Sequences)
					</h1>
					<p className="text-sm text-muted-foreground">
						Quản lý các chuỗi email nuôi dưỡng khách hàng tiềm năng theo khung giờ hợp pháp Việt Nam
					</p>
				</div>
				<div className="flex items-center gap-3">
					<button
						type="button"
						onClick={fetchSequences}
						className="p-2 border rounded-lg hover:bg-accent text-muted-foreground transition-colors"
						title="Tải lại"
					>
						<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
					</button>
					<Link
						href={`/dashboard/${workspaceId}/automations/campaigns/new`}
						className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm text-sm"
					>
						<Plus className="w-4 h-4" aria-hidden="true" />
						Tạo chiến dịch mới
					</Link>
				</div>
			</div>

			{loading ? (
				<div className="p-12 text-center text-muted-foreground text-sm">
					Đang tải danh sách chiến dịch...
				</div>
			) : sequences.length === 0 ? (
				<div className="bg-card border rounded-xl p-12 text-center space-y-4">
					<div className="w-12 h-12 rounded-full bg-primary/10 text-primary mx-auto flex items-center justify-center">
						<Send className="w-6 h-6" aria-hidden="true" />
					</div>
					<div className="space-y-1">
						<h3 className="text-base font-semibold text-foreground">
							Chưa có chiến dịch tiếp cận nào
						</h3>
						<p className="text-sm text-muted-foreground max-w-md mx-auto">
							Bắt đầu tự động hóa gửi chuỗi email chăm sóc khách hàng với bộ quy tắc thời gian chờ
							và điều kiện thông minh.
						</p>
					</div>
					<Link
						href={`/dashboard/${workspaceId}/automations/campaigns/new`}
						className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm text-sm"
					>
						<Plus className="w-4 h-4" aria-hidden="true" />
						Bắt đầu tạo chiến dịch đầu tiên
					</Link>
				</div>
			) : (
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
					{sequences.map((seq) => (
						<div
							key={seq.id}
							className="bg-card border rounded-xl p-5 shadow-sm space-y-4 flex flex-col justify-between"
						>
							<div className="space-y-2">
								<div className="flex items-center justify-between">
									<span
										className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
											seq.status === "active"
												? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
												: "bg-amber-500/10 text-amber-600 border border-amber-500/20"
										}`}
									>
										{seq.status === "active" ? "Đang chạy" : "Tạm dừng"}
									</span>
									<span className="text-xs text-muted-foreground flex items-center gap-1">
										<Clock className="w-3.5 h-3.5" aria-hidden="true" />
										{new Date(seq.created_at).toLocaleDateString("vi-VN")}
									</span>
								</div>

								<h3 className="font-semibold text-foreground line-clamp-1">{seq.name}</h3>
								{seq.description && (
									<p className="text-xs text-muted-foreground line-clamp-2">{seq.description}</p>
								)}
							</div>

							<div className="border-t pt-3 flex items-center justify-between text-sm">
								<button
									type="button"
									onClick={() => toggleStatus(seq)}
									className="text-xs font-medium inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
								>
									{seq.status === "active" ? (
										<>
											<Pause className="w-3.5 h-3.5" aria-hidden="true" /> Tạm dừng
										</>
									) : (
										<>
											<Play className="w-3.5 h-3.5" aria-hidden="true" /> Kích hoạt
										</>
									)}
								</button>

								<Link
									href={`/dashboard/${workspaceId}/automations/campaigns/${seq.id}`}
									className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
								>
									<BarChart3 className="w-3.5 h-3.5" aria-hidden="true" />
									Chi tiết & Thống kê
								</Link>
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
