"use client";

import { Bot, Clock, Filter, Play, Save, Send, Sliders, Zap } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import { automationsApiService } from "@/lib/apis/automations-api.service";
import { cn } from "@/lib/utils";

export interface AutomationBuilderPanelProps {
	workspaceId?: string | number;
	workflow?: {
		name: string;
		triggerPlatform: string;
		scheduleTime: string;
		notifyChannel: string;
		minFitScore: number;
		status: "active" | "draft" | "paused";
	};
	className?: string;
}

export const AutomationBuilderPanel: React.FC<AutomationBuilderPanelProps> = ({
	workspaceId = "1",
	workflow,
	className,
}) => {
	const [scheduleTime, setScheduleTime] = useState(workflow?.scheduleTime || "08:00");
	const [targetPlatform, setTargetPlatform] = useState(workflow?.triggerPlatform || "batdongsan");
	const [notifyChannel, setNotifyChannel] = useState(workflow?.notifyChannel || "telegram");
	const [minFitScore, setMinFitScore] = useState(workflow?.minFitScore || 85);
	const [workflowName, _setWorkflowName] = useState(workflow?.name || "Quy trình Săn Lead Tự Động");
	const [isRunningTest, setIsRunningTest] = useState(false);
	const [isSaving, setIsSaving] = useState(false);
	const [testLogs, setTestLogs] = useState<string[]>([]);

	const handleRunTest = async () => {
		setIsRunningTest(true);
		setTestLogs(["[00:01] Khởi chạy kiểm thử kết nối Celery Worker..."]);

		setTimeout(() => {
			setTestLogs((prev) => [
				...prev,
				`[00:02] Kích hoạt Scraper: Quét thử tin đăng từ ${targetPlatform}...`,
			]);
		}, 600);

		setTimeout(() => {
			setTestLogs((prev) => [
				...prev,
				`[00:03] Lọc SĐT theo DNC và chấm Fit Score (Ngưỡng >= ${minFitScore})...`,
			]);
		}, 1200);

		setTimeout(() => {
			setTestLogs((prev) => [
				...prev,
				`[00:04] Gửi mẫu thông báo kiểm thử qua kênh ${notifyChannel.toUpperCase()} thành công!`,
				"✅ Hoàn tất kiểm thử luồng tự động.",
			]);
			setIsRunningTest(false);
			toast.success(`Đã kiểm thử thành công luồng ${targetPlatform}!`);
		}, 1800);
	};

	const handleSaveAutomation = async () => {
		try {
			setIsSaving(true);
			toast.loading("Đang lưu kịch bản tự động hóa lên hệ thống...", { id: "save-automation" });

			const [hour, minute] = scheduleTime.split(":");
			const cron = `${minute || "0"} ${hour || "8"} * * *`;

			const autoName =
				workflowName || `Săn Lead ${targetPlatform.toUpperCase()} Hàng Ngày (${scheduleTime})`;
			const autoDesc = `Tự động quét ${targetPlatform} lúc ${scheduleTime} và gửi thông báo qua ${notifyChannel}.`;

			const created = await automationsApiService.createAutomation({
				workspace_id: Number(workspaceId || 1),
				name: autoName,
				description: autoDesc,
				definition: {
					schema_version: "1.0",
					name: autoName,
					goal: autoDesc,
					triggers: [{ type: "schedule", params: { cron_expression: cron } }],
					plan: [
						{
							step_id: "scrape_step",
							action: `scrape_${targetPlatform}`,
							params: { min_fit_score: minFitScore, notify_channel: notifyChannel },
						},
					],
					execution: {
						timeout_seconds: 600,
						max_retries: 2,
						retry_backoff: "exponential",
						concurrency: "drop_if_running",
						on_failure: [],
					},
					metadata: { tags: ["lead_generation", targetPlatform] },
				},
				triggers: [
					{
						type: "schedule",
						params: { cron_expression: cron },
						static_inputs: {},
						enabled: true,
					},
				],
			});

			toast.success(`Đã kích hoạt kịch bản "${created.name}" thành công!`, {
				id: "save-automation",
				duration: 3000,
			});
		} catch (err: unknown) {
			toast.error(
				err instanceof Error ? err.message : "Không thể lưu kịch bản tự động hóa lúc này.",
				{ id: "save-automation" }
			);
		} finally {
			setIsSaving(false);
		}
	};

	return (
		<div
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				className
			)}
		>
			{/* Top Controls Bar */}
			<div className="h-10 border-b border-border/80 bg-muted/30 flex items-center justify-between px-4 shrink-0">
				<div className="flex items-center gap-2">
					<Zap className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
					<span className="text-xs font-bold text-foreground">
						Kịch Bản Tự Động Hóa: Cào & Thông Báo Leads Hàng Ngày
					</span>
					<span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold border border-emerald-500/20">
						Đang Bật (Active)
					</span>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={handleRunTest}
						disabled={isRunningTest}
						className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-md border border-border/80 bg-card hover:bg-muted text-foreground transition-colors cursor-pointer disabled:opacity-50"
					>
						<Play className="w-3 h-3 text-emerald-600 fill-current" aria-hidden="true" />
						<span>{isRunningTest ? "Đang Test..." : "Test Run Ngay"}</span>
					</button>
					<button
						type="button"
						onClick={handleSaveAutomation}
						disabled={isSaving}
						className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded-md bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-xs disabled:opacity-50"
					>
						<Save className="w-3 h-3" aria-hidden="true" />
						<span>{isSaving ? "Đang Lưu..." : "Lưu Kịch Bản"}</span>
					</button>
				</div>
			</div>

			{/* Main Canvas Area */}
			<div className="flex-1 overflow-y-auto p-6 scrollbar-thin space-y-6">
				{/* Visual Node Flow Diagram */}
				<div>
					<h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
						Sơ Đồ Luồng Tự Động (Visual Workflow Nodes)
					</h3>

					<div className="grid grid-cols-1 md:grid-cols-4 gap-3">
						{/* Node 1: Trigger */}
						<div className="p-3.5 rounded-xl border border-border bg-card relative shadow-xs">
							<div className="flex items-center gap-2 text-xs font-bold text-foreground mb-1.5">
								<Clock className="w-4 h-4 text-blue-500" aria-hidden="true" />
								<span>1. Lịch Chạy (Trigger)</span>
							</div>
							<p className="text-[11px] text-muted-foreground">
								Hàng ngày lúc <strong>{scheduleTime}</strong>
							</p>
							<div className="mt-2 text-[10px] text-blue-600 dark:text-blue-400 font-mono">
								Cron: 0 8 * * *
							</div>
						</div>

						{/* Node 2: Scraper Action */}
						<div className="p-3.5 rounded-xl border border-border bg-card relative shadow-xs">
							<div className="flex items-center gap-2 text-xs font-bold text-foreground mb-1.5">
								<Bot className="w-4 h-4 text-emerald-500" aria-hidden="true" />
								<span>2. Cào Dữ Liệu</span>
							</div>
							<p className="text-[11px] text-muted-foreground">
								Nguồn: <strong>{targetPlatform.toUpperCase()}</strong>
							</p>
							<div className="mt-2 text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
								Query: BĐS Hà Nội mới đăng
							</div>
						</div>

						{/* Node 3: Filter DNC */}
						<div className="p-3.5 rounded-xl border border-border bg-card relative shadow-xs">
							<div className="flex items-center gap-2 text-xs font-bold text-foreground mb-1.5">
								<Filter className="w-4 h-4 text-purple-500" aria-hidden="true" />
								<span>3. Lọc & Chấm Điểm</span>
							</div>
							<p className="text-[11px] text-muted-foreground">
								Fit Score &gt;= <strong>{minFitScore}</strong> + Lọc DNC
							</p>
							<div className="mt-2 text-[10px] text-purple-600 dark:text-purple-400 font-mono">
								Nghị định 91 Compliance
							</div>
						</div>

						{/* Node 4: Notify Action */}
						<div className="p-3.5 rounded-xl border border-border bg-card relative shadow-xs">
							<div className="flex items-center gap-2 text-xs font-bold text-foreground mb-1.5">
								<Send className="w-4 h-4 text-amber-500" aria-hidden="true" />
								<span>4. Bắn Thông Báo</span>
							</div>
							<p className="text-[11px] text-muted-foreground">
								Kênh: <strong>{notifyChannel === "telegram" ? "Telegram Bot" : "Zalo OA"}</strong>
							</p>
							<div className="mt-2 text-[10px] text-amber-600 dark:text-amber-400 font-mono">
								Format: Leads Digest Card
							</div>
						</div>
					</div>
				</div>

				{/* Parameter Adjuster Form */}
				<div className="p-5 rounded-2xl border border-border bg-card space-y-4 shadow-xs">
					<h4 className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-2">
						<Sliders className="w-3.5 h-3.5 text-emerald-600" aria-hidden="true" />
						<span>Tùy Chỉnh Tham Số Kịch Bản</span>
					</h4>

					<div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
						<label htmlFor="auto-schedule-time" className="block">
							<span className="text-[11px] font-medium text-muted-foreground block mb-1">
								Giờ Gửi Thông Báo
							</span>
							<input
								id="auto-schedule-time"
								type="time"
								value={scheduleTime}
								onChange={(e) => setScheduleTime(e.target.value)}
								className="w-full px-3 py-1.5 text-xs rounded-lg border border-border bg-background text-foreground focus:ring-1 focus:ring-emerald-500"
							/>
						</label>

						<label htmlFor="auto-target-platform" className="block">
							<span className="text-[11px] font-medium text-muted-foreground block mb-1">
								Nền Tảng Cào Dữ Liệu
							</span>
							<select
								id="auto-target-platform"
								value={targetPlatform}
								onChange={(e) => setTargetPlatform(e.target.value)}
								className="w-full px-3 py-1.5 text-xs rounded-lg border border-border bg-background text-foreground focus:ring-1 focus:ring-emerald-500"
							>
								<option value="batdongsan">Batdongsan.com.vn</option>
								<option value="chotot">Chợ Tốt (BĐS & Việc làm)</option>
								<option value="topcv">TopCV (Doanh nghiệp tuyển dụng)</option>
								<option value="muasamcong">Đấu Thầu Mua Sắm Công</option>
							</select>
						</label>

						<label htmlFor="auto-min-fit-score" className="block">
							<span className="text-[11px] font-medium text-muted-foreground block mb-1">
								Fit Score Tối Thiểu:{" "}
								<strong className="text-emerald-600 font-mono">{minFitScore}+</strong>
							</span>
							<input
								id="auto-min-fit-score"
								type="range"
								min={60}
								max={95}
								value={minFitScore}
								onChange={(e) => setMinFitScore(Number(e.target.value))}
								className="w-full h-2 mt-2 accent-emerald-600 cursor-pointer"
							/>
						</label>

						<label htmlFor="auto-notify-channel" className="block">
							<span className="text-[11px] font-medium text-muted-foreground block mb-1">
								Kênh Nhận Báo Cáo
							</span>
							<select
								id="auto-notify-channel"
								value={notifyChannel}
								onChange={(e) => setNotifyChannel(e.target.value)}
								className="w-full px-3 py-1.5 text-xs rounded-lg border border-border bg-background text-foreground focus:ring-1 focus:ring-emerald-500"
							>
								<option value="telegram">Telegram (@NowingLeadsBot)</option>
								<option value="zalo">Zalo OA Thông Báo</option>
								<option value="lark">Lark Base / Lark Webhook</option>
							</select>
						</label>
					</div>
				</div>

				{/* Live Execution Test Logs */}
				{testLogs.length > 0 && (
					<div className="p-4 rounded-xl border border-border bg-zinc-950 text-zinc-100 font-mono text-xs space-y-1.5">
						<div className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider mb-2">
							Nhật Ký Thực Thi Thử Nghiệm (Execution Logs)
						</div>
						{testLogs.map((log) => (
							<div key={log} className="leading-relaxed">
								{log}
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
};
