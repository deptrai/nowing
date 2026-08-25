"use client";

import {
	ArrowLeft,
	BarChart3,
	CheckCircle2,
	Clock,
	Coins,
	Mail,
	MessageSquare,
	RefreshCw,
	UserMinus,
	Users,
	XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type {
	Sequence,
	SequenceAnalytics,
	SequenceEnrollment,
	SequenceEvent,
	SequenceStep,
} from "@/contracts/types/sequence.types";
import { sequenceApiService } from "@/lib/apis/sequence-api.service";

export default function CampaignAnalyticsPage() {
	const params = useParams();
	const workspaceId = Number(params?.workspace_id);
	const sequenceId = String(params?.sequence_id || "");

	const [sequence, setSequence] = useState<Sequence | null>(null);
	const [analytics, setAnalytics] = useState<SequenceAnalytics | null>(null);
	const [enrollments, setEnrollments] = useState<SequenceEnrollment[]>([]);
	const [events, setEvents] = useState<SequenceEvent[]>([]);
	const [loading, setLoading] = useState(true);

	const loadData = useCallback(async () => {
		if (!sequenceId || Number.isNaN(workspaceId)) return;
		setLoading(true);
		try {
			const [seqData, analyticsData, enrollmentsData, eventsData] = await Promise.all([
				sequenceApiService.getSequence(workspaceId, sequenceId).catch(() => null),
				sequenceApiService.getAnalytics(workspaceId, sequenceId).catch(() => null),
				sequenceApiService.listEnrollments(workspaceId, sequenceId).catch(() => []),
				sequenceApiService.listEvents(workspaceId, sequenceId).catch(() => []),
			]);
			setSequence(seqData);
			setAnalytics(analyticsData);
			setEnrollments(enrollmentsData);
			setEvents(eventsData);
		} catch (err) {
			console.error("Failed to load campaign data:", err);
		} finally {
			setLoading(false);
		}
	}, [workspaceId, sequenceId]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	if (Number.isNaN(workspaceId)) {
		return (
			<div className="p-6 max-w-6xl mx-auto text-sm text-destructive">
				Workspace ID không hợp lệ.
			</div>
		);
	}

	return (
		<div className="p-6 space-y-6 max-w-6xl mx-auto">
			{/* Top Header */}
			<div className="flex items-center justify-between" data-testid="sequence-analytics-header">
				<div className="flex items-center gap-3">
					<Link
						href={`/dashboard/${workspaceId}/automations/campaigns`}
						className="p-2 border rounded-lg hover:bg-accent text-muted-foreground transition-colors"
					>
						<ArrowLeft className="w-4 h-4" aria-hidden="true" />
					</Link>
					<div>
						<h1 className="text-xl font-bold text-foreground">
							{sequence?.name || "Chi tiết & Báo cáo Chiến dịch"}
						</h1>
						<p className="text-xs text-muted-foreground">
							{sequence?.description ||
								"Theo dõi chuyển đổi, phản hồi và ngân sách gửi email theo thời gian thực"}
						</p>
					</div>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={loadData}
						className="p-2 border rounded-lg hover:bg-accent text-muted-foreground transition-colors"
						title="Làm mới"
					>
						<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
					</button>
				</div>
			</div>

			{/* Metric Cards Grid */}
			<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-4">
				<div
					data-testid="metric-total-enrolled"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Tổng tham gia</span>
						<Users className="w-4 h-4 text-blue-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						{analytics?.total_enrolled ?? enrollments.length}
					</div>
				</div>

				<div
					data-testid="metric-active-scheduled"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Đang lên lịch</span>
						<Clock className="w-4 h-4 text-amber-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						{analytics?.active_scheduled ?? 0}
					</div>
				</div>

				<div
					data-testid="metric-delivered-count"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Đã gửi thành công</span>
						<Mail className="w-4 h-4 text-emerald-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						{analytics?.delivered_count ?? 0}
					</div>
				</div>

				<div
					data-testid="metric-responded-count"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Đã phản hồi</span>
						<MessageSquare className="w-4 h-4 text-purple-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						{analytics?.responded_count ?? 0}
					</div>
				</div>

				<div
					data-testid="metric-unsubscribed-count"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Đã hủy đăng ký</span>
						<UserMinus className="w-4 h-4 text-rose-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						{analytics?.unsubscribed_count ?? 0}
					</div>
				</div>

				<div
					data-testid="metric-failed-count"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Thất bại</span>
						<XCircle className="w-4 h-4 text-red-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">{analytics?.failed_count ?? 0}</div>
				</div>

				<div
					data-testid="metric-total-cost"
					className="bg-card border rounded-xl p-4 shadow-sm space-y-1.5"
				>
					<div className="flex items-center justify-between text-muted-foreground">
						<span className="text-xs font-medium">Tổng chi phí</span>
						<Coins className="w-4 h-4 text-indigo-500" aria-hidden="true" />
					</div>
					<div className="text-2xl font-bold text-foreground">
						${((analytics?.total_cost_micros ?? 0) / 1_000_000 || 0).toFixed(3)}
					</div>
				</div>
			</div>

			{/* Channel Breakdown */}
			<div className="bg-card border rounded-xl p-5 shadow-sm space-y-4">
				<h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
					<BarChart3 className="w-4 h-4 text-primary" aria-hidden="true" />
					Phân tích theo kênh (Channel Breakdown)
				</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
					{analytics?.channel_breakdown && analytics.channel_breakdown.length > 0 ? (
						analytics.channel_breakdown.map((cb) => (
							<div
								key={cb.channel}
								className="p-3 border rounded-lg bg-background text-sm space-y-1"
							>
								<div className="flex items-center justify-between font-medium">
									<span className="capitalize">{cb.channel}</span>
									<span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
										${(cb.cost_micros / 1_000_000).toFixed(3)}
									</span>
								</div>
								<div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
									<span>Sent: {cb.sent}</span>
									<span>Replied: {cb.replied}</span>
									<span>Failed: {cb.failed}</span>
								</div>
							</div>
						))
					) : (
						<div className="text-center py-6 text-muted-foreground text-xs">
							Chưa có dữ liệu phân tích theo kênh
						</div>
					)}
				</div>
			</div>

			{/* Steps Breakdown & Live Logs */}
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				{/* Steps Config */}
				<div className="bg-card border rounded-xl p-5 shadow-sm space-y-4">
					<h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
						<BarChart3 className="w-4 h-4 text-primary" aria-hidden="true" />
						Cấu hình các bước trong chuỗi
					</h3>
					<div className="space-y-3">
						{sequence?.steps && sequence.steps.length > 0 ? (
							sequence.steps.map((step: SequenceStep) => (
								<div
									key={step.step_order}
									className="p-3 border rounded-lg bg-background text-sm space-y-1"
								>
									<div className="flex items-center justify-between font-medium">
										<span>
											Bước {step.step_order}:{" "}
											{step.step_type === "send_email"
												? "Gửi Email"
												: step.step_type === "wait"
													? "Thời gian chờ"
													: "Điều kiện"}
										</span>
										<span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground capitalize">
											{step.channel}
										</span>
									</div>
									{step.template?.subject && (
										<p className="text-xs text-muted-foreground line-clamp-1">
											Tiêu đề: {step.template.subject}
										</p>
									)}
								</div>
							))
						) : (
							<div className="text-center py-6 text-muted-foreground text-xs">
								Chưa có bước nào trong chuỗi
							</div>
						)}
					</div>
				</div>

				{/* Recent Events Log */}
				<div className="bg-card border rounded-xl p-5 shadow-sm space-y-4">
					<h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
						<CheckCircle2 className="w-4 h-4 text-emerald-500" aria-hidden="true" />
						Nhật ký tương tác gần đây (Sequence Events)
					</h3>
					<div className="space-y-2 max-h-96 overflow-y-auto">
						{events.length > 0 ? (
							events.map((ev) => (
								<div
									key={ev.id}
									className="p-2.5 border rounded-lg bg-background text-xs flex items-center justify-between"
								>
									<div className="flex items-center gap-2">
										<span className="px-2 py-0.5 rounded bg-primary/10 text-primary font-semibold capitalize">
											{ev.event_type}
										</span>
										<span className="text-muted-foreground">Kênh: {ev.channel}</span>
									</div>
									<span className="text-muted-foreground">
										{new Date(ev.created_at).toLocaleTimeString("vi-VN")}
									</span>
								</div>
							))
						) : (
							<div className="text-center py-8 text-muted-foreground text-xs">
								Chưa có nhật ký gửi nào
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}
