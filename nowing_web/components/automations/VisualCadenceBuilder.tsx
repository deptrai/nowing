"use client";

import {
	Clock,
	GitBranch,
	Info,
	Mail,
	MessageSquare,
	Plus,
	Save,
	Send,
	ShieldCheck,
	Trash2,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
import type { SequenceCreate, SequenceStep } from "../../contracts/types/sequence.types";

interface VisualCadenceBuilderProps {
	workspaceId?: number | string;
	initialSequence?: Partial<SequenceCreate>;
	onSave: (payload: SequenceCreate) => Promise<void>;
	isSaving?: boolean;
	// Feature gate injected by parent page.
	ad41Reactivated?: boolean;
	outboundChannels?: string[];
}

const TEMPLATE_VARIABLES = [
	{ label: "{customer_name}", desc: "Tên khách hàng / liên hệ" },
	{ label: "{company}", desc: "Tên công ty / doanh nghiệp" },
	{ label: "{property_title}", desc: "Tiêu đề BĐS / bài đăng" },
	{ label: "{consultant_phone}", desc: "Hotline chuyên viên" },
];

const PARSE_MODES = [
	{ value: "", label: "Plain text (MarkdownV2 auto-fallback)" },
	{ value: "MarkdownV2", label: "MarkdownV2" },
	{ value: "HTML", label: "HTML" },
];

type StepType = "send_email" | "send_zalo" | "send_telegram" | "wait" | "condition";
type Channel = "email" | "zalo" | "telegram";

export const VisualCadenceBuilder: React.FC<VisualCadenceBuilderProps> = ({
	initialSequence,
	onSave,
	isSaving = false,
	ad41Reactivated = false,
	outboundChannels = ["email"],
}) => {
	const [name, setName] = useState(initialSequence?.name || "Chiến dịch tiếp cận tự động");
	const [description, setDescription] = useState(initialSequence?.description || "");

	const allowedSet = useMemo(
		() => new Set(outboundChannels.map((c) => c.toLowerCase())),
		[outboundChannels]
	);

	const [steps, setSteps] = useState<SequenceStep[]>(
		initialSequence?.steps || [
			{
				step_order: 1,
				step_type: "send_email",
				channel: "email",
				template: {
					subject: "Cơ hội hợp tác đầu tư {property_title}",
					body: "Kính gửi {customer_name},\n\nTôi thấy doanh nghiệp {company} đang quan tâm đến cơ hội đầu tư. Chúng tôi xin gửi thông tin chi tiết qua hotline {consultant_phone}.\n\nTrân trọng,",
				},
				fallback_channels: [],
				condition_config: {},
				is_enabled: true,
			},
		]
	);

	const [templateDataErrors, setTemplateDataErrors] = useState<Record<number, string>>({});

	const defaultFallbacks = (channel: Channel): Channel[] => {
		switch (channel) {
			case "zalo":
				return ["telegram", "email"];
			case "telegram":
				return ["email"];
			default:
				return [];
		}
	};

	const handleAddStep = (type: StepType) => {
		const nextOrder = steps.length + 1;
		let newStep: SequenceStep;

		if (type === "send_email") {
			newStep = {
				step_order: nextOrder,
				step_type: "send_email",
				channel: "email",
				template: {
					subject: "Theo dõi phản hồi từ {customer_name}",
					body: "Chào {customer_name}, tôi muốn kiểm tra xem bạn đã nhận được email trước của tôi chưa?",
				},
				fallback_channels: defaultFallbacks("email"),
				condition_config: {},
				is_enabled: true,
			};
		} else if (type === "send_zalo") {
			newStep = {
				step_order: nextOrder,
				step_type: "send_zalo",
				channel: "zalo",
				template: {
					template_id: "ZNS_OUTREACH_APPROVED_01",
					template_data: { customer_name: "{customer_name}", property_title: "{property_title}" },
					body: "Xin chào {customer_name}, chuyên viên Nowing xin gửi thông tin tư vấn theo yêu cầu của bạn.",
				},
				fallback_channels: defaultFallbacks("zalo"),
				condition_config: {},
				is_enabled: true,
			};
		} else if (type === "send_telegram") {
			newStep = {
				step_order: nextOrder,
				step_type: "send_telegram",
				channel: "telegram",
				template: {
					body: "Chào {customer_name}, mình gửi bạn bảng tính lợi nhuận cho {property_title}. Cần hỗ trợ liên hệ {consultant_phone} nhé!",
					parse_mode: "",
				},
				fallback_channels: defaultFallbacks("telegram"),
				condition_config: {},
				is_enabled: true,
			};
		} else if (type === "wait") {
			newStep = {
				step_order: nextOrder,
				step_type: "wait",
				channel: "email",
				wait_duration_seconds: 172800, // 2 days
				template: {},
				condition_config: {},
				is_enabled: true,
			};
		} else {
			newStep = {
				step_order: nextOrder,
				step_type: "condition",
				channel: "email",
				condition_config: {
					predicate: "has_replied",
					if_true_step: null, // Exit if replied
					if_false_step: nextOrder + 1,
				},
				template: {},
				is_enabled: true,
			};
		}

		setSteps([...steps, newStep]);
	};

	const handleRemoveStep = (index: number) => {
		const updated = steps
			.filter((_, idx) => idx !== index)
			.map((step, idx) => ({ ...step, step_order: idx + 1 }));
		setSteps(updated);
	};

	const handleUpdateStep = (index: number, patch: Partial<SequenceStep>) => {
		const updated = [...steps];
		updated[index] = { ...updated[index], ...patch };
		setSteps(updated);
	};

	const handleUpdateTemplate = (index: number, templatePatch: Record<string, unknown>) => {
		const step = steps[index];
		handleUpdateStep(index, {
			template: { ...step.template, ...templatePatch },
		});
	};

	const insertVariable = (index: number, variable: string) => {
		const currentStep = steps[index];
		const currentBody = currentStep.template?.body || "";
		handleUpdateTemplate(index, { body: `${currentBody} ${variable}` });
	};

	const toggleFallbackChannel = (index: number, channel: Channel) => {
		const currentFallbacks = steps[index].fallback_channels || [];
		const nextFallbacks = currentFallbacks.includes(channel)
			? currentFallbacks.filter((c) => c !== channel)
			: [...currentFallbacks, channel];
		handleUpdateStep(index, { fallback_channels: nextFallbacks });
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		// Sanitize: wait/condition steps should not carry a real channel.
		const cleanSteps = steps.map((step) => ({
			...step,
			channel: step.step_type === "wait" || step.step_type === "condition" ? "email" : step.channel,
		}));
		const payload: SequenceCreate = {
			name,
			description,
			status: "active",
			shared: false,
			entry_step_order: 1,
			steps: cleanSteps,
		};
		await onSave(payload);
	};

	const isChannelAllowed = (channel: Channel) => allowedSet.has(channel);

	return (
		<div className="space-y-6" data-testid="sequence-cadence-builder">
			{/* Top Header Card */}
			<div className="bg-card border rounded-xl p-6 shadow-sm space-y-4">
				<div className="flex items-center justify-between">
					<div>
						<div className="flex items-center gap-2">
							<h2 className="text-xl font-semibold text-foreground">
								Visual Multi-Channel Cadence Sequence Builder
							</h2>
							<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
								<ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" /> Story 24.7 Multi-Channel
							</span>
						</div>
						<p className="text-sm text-muted-foreground mt-1">
							Thiết lập quy trình tiếp cận khách hàng tự động đa kênh (Zalo ZNS + Telegram + Email
							Cadence, tuân thủ khung giờ 08:00 - 21:30 VN Time)
						</p>
					</div>
					<button
						type="button"
						onClick={handleSubmit}
						disabled={isSaving || steps.length === 0 || Object.keys(templateDataErrors).length > 0}
						data-testid="save-sequence-btn"
						className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
					>
						<Save className="w-4 h-4" aria-hidden="true" />
						{isSaving ? "Đang lưu..." : "Lưu chuỗi tiếp cận"}
					</button>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
					<div>
						<label
							htmlFor="campaign-name-input"
							className="block text-xs font-semibold text-foreground uppercase tracking-wider mb-1"
						>
							Tên chiến dịch
						</label>
						<input
							id="campaign-name-input"
							type="text"
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder="VD: Drip Nuôi dưỡng Khách hàng VIP BĐS"
							className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
							maxLength={255}
							required
						/>
					</div>
					<div>
						<label
							htmlFor="campaign-desc-input"
							className="block text-xs font-semibold text-foreground uppercase tracking-wider mb-1"
						>
							Mô tả mục tiêu
						</label>
						<input
							id="campaign-desc-input"
							type="text"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="VD: Gửi chuỗi Zalo ZNS + Telegram + Email theo dõi phản hồi với khoảng cách 48h"
							className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
						/>
					</div>
				</div>

				{/* Outbound Channel Gate (AD-41 / DEF-102) */}
				<div className="pt-2">
					<span className="block text-xs font-semibold text-foreground uppercase tracking-wider mb-2">
						Kênh tiếp cận được bật (Outbound Channels)
					</span>
					<div className="flex flex-wrap gap-3">
						<ChannelChip channel="email" allowed={isChannelAllowed("email")} />
						<ChannelChip
							channel="zalo"
							allowed={isChannelAllowed("zalo") && ad41Reactivated}
							disabledReason={
								!ad41Reactivated
									? "Deferred — AD-41 / DEF-102"
									: !isChannelAllowed("zalo")
										? "Not enabled for this workspace"
										: undefined
							}
						/>
						<ChannelChip
							channel="telegram"
							allowed={isChannelAllowed("telegram")}
							disabledReason={
								!isChannelAllowed("telegram") ? "Not enabled for this workspace" : undefined
							}
						/>
					</div>
				</div>
			</div>

			{/* Timeline Step Nodes */}
			<div className="space-y-4">
				{steps.map((step, index) => {
					const stepKey = `step-${step.step_order}-${step.step_type}`;
					return (
						<div
							key={stepKey}
							data-testid={`step-node-${index + 1}`}
							className="bg-card border rounded-xl p-5 shadow-sm space-y-4 relative"
						>
							<div className="flex items-center justify-between border-b pb-3">
								<div className="flex items-center gap-3">
									<span className="flex items-center justify-center w-7 h-7 rounded-full bg-primary/10 text-primary font-bold text-xs">
										{step.step_order}
									</span>
									<h3 className="text-sm font-semibold capitalize flex items-center gap-2">
										{step.step_type === "send_email" && (
											<>
												<Mail className="w-4 h-4 text-blue-500" aria-hidden="true" />
												Bước gửi Email
											</>
										)}
										{step.step_type === "send_zalo" && (
											<>
												<MessageSquare className="w-4 h-4 text-blue-600" aria-hidden="true" />
												Bước gửi Zalo ZNS
											</>
										)}
										{step.step_type === "send_telegram" && (
											<>
												<Send className="w-4 h-4 text-sky-500" aria-hidden="true" />
												Bước gửi Telegram
											</>
										)}
										{step.step_type === "wait" && (
											<>
												<Clock className="w-4 h-4 text-amber-500" aria-hidden="true" />
												Thời gian chờ (Wait / Delay)
											</>
										)}
										{step.step_type === "condition" && (
											<>
												<GitBranch className="w-4 h-4 text-purple-500" aria-hidden="true" />
												Điều kiện rẽ nhánh (if replied)
											</>
										)}
									</h3>
								</div>

								{steps.length > 1 && (
									<button
										type="button"
										onClick={() => handleRemoveStep(index)}
										className="text-muted-foreground hover:text-destructive transition-colors p-1"
										title="Xóa bước này"
									>
										<Trash2 className="w-4 h-4" aria-hidden="true" />
									</button>
								)}
							</div>

							{/* Step Type Configs */}
							{step.step_type === "send_email" && (
								<div className="space-y-3">
									<div>
										<label
											htmlFor={`email-subject-input-${step.step_order}`}
											className="block text-xs font-medium text-muted-foreground mb-1"
										>
											Tiêu đề Email (Subject)
										</label>
										<input
											id={`email-subject-input-${step.step_order}`}
											type="text"
											value={(step.template?.subject as string) || ""}
											onChange={(e) => handleUpdateTemplate(index, { subject: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
										/>
									</div>

									<div>
										<div className="flex items-center justify-between mb-1">
											<label
												htmlFor={`email-body-input-${step.step_order}`}
												className="block text-xs font-medium text-muted-foreground"
											>
												Nội dung Email (Body)
											</label>
											<TemplateVariables onInsert={(v) => insertVariable(index, v)} />
										</div>
										<textarea
											id={`email-body-input-${step.step_order}`}
											rows={4}
											value={(step.template?.body as string) || ""}
											onChange={(e) => handleUpdateTemplate(index, { body: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none font-mono text-xs"
										/>
									</div>
								</div>
							)}

							{step.step_type === "send_zalo" && (
								<div className="space-y-3">
									<div>
										<label
											htmlFor={`zalo-template-id-${step.step_order}`}
											className="block text-xs font-medium text-muted-foreground mb-1"
										>
											Zalo ZNS Template ID (Đã duyệt bởi VNG)
										</label>
										<input
											id={`zalo-template-id-${step.step_order}`}
											type="text"
											value={(step.template?.template_id as string) || "ZNS_OUTREACH_APPROVED_01"}
											onChange={(e) => handleUpdateTemplate(index, { template_id: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none font-mono text-xs"
										/>
									</div>

									<div>
										<label
											htmlFor={`zalo-template-data-${step.step_order}`}
											className="block text-xs font-medium text-muted-foreground mb-1"
										>
											Template Data (JSON mapping cho ZNS)
										</label>
										<textarea
											id={`zalo-template-data-${step.step_order}`}
											rows={3}
											value={JSON.stringify(step.template?.template_data || {}, null, 2)}
											onChange={(e) => {
												try {
													const parsed = JSON.parse(e.target.value);
													handleUpdateTemplate(index, { template_data: parsed });
													setTemplateDataErrors((prev) => {
														const next = { ...prev };
														delete next[index];
														return next;
													});
												} catch {
													setTemplateDataErrors((prev) => ({
														...prev,
														[index]: "JSON không hợp lệ — vui lòng sửa trước khi lưu.",
													}));
												}
											}}
											className={`w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none font-mono text-xs ${
												templateDataErrors[index] ? "border-destructive focus:ring-destructive" : ""
											}`}
										/>
										{templateDataErrors[index] && (
											<p className="text-xs text-destructive mt-1">{templateDataErrors[index]}</p>
										)}
									</div>

									<div>
										<label
											htmlFor={`zalo-body-input-${step.step_order}`}
											className="block text-xs font-medium text-muted-foreground mb-1"
										>
											Nội dung mẫu / Thông điệp ZNS (preview)
										</label>
										<textarea
											id={`zalo-body-input-${step.step_order}`}
											rows={3}
											value={(step.template?.body as string) || ""}
											onChange={(e) => handleUpdateTemplate(index, { body: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none text-xs"
										/>
									</div>
								</div>
							)}

							{step.step_type === "send_telegram" && (
								<div className="space-y-3">
									<div>
										<label
											htmlFor={`telegram-parse-mode-${step.step_order}`}
											className="block text-xs font-medium text-muted-foreground mb-1"
										>
											Parse Mode
										</label>
										<select
											id={`telegram-parse-mode-${step.step_order}`}
											value={(step.template?.parse_mode as string) || ""}
											onChange={(e) => handleUpdateTemplate(index, { parse_mode: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
										>
											{PARSE_MODES.map((m) => (
												<option key={m.value} value={m.value}>
													{m.label}
												</option>
											))}
										</select>
									</div>

									<div>
										<div className="flex items-center justify-between mb-1">
											<label
												htmlFor={`telegram-body-input-${step.step_order}`}
												className="block text-xs font-medium text-muted-foreground"
											>
												Nội dung tin nhắn Telegram
											</label>
											<TemplateVariables onInsert={(v) => insertVariable(index, v)} />
										</div>
										<textarea
											id={`telegram-body-input-${step.step_order}`}
											rows={3}
											value={(step.template?.body as string) || ""}
											onChange={(e) => handleUpdateTemplate(index, { body: e.target.value })}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none text-xs"
										/>
									</div>
								</div>
							)}

							{/* Fallback Channels Configuration for Outreach Steps */}
							{["send_email", "send_zalo", "send_telegram"].includes(step.step_type) && (
								<div className="pt-2 border-t border-border/50">
									<span className="block text-xs font-semibold text-muted-foreground mb-1.5">
										Kênh dự phòng tự động (Fallback Channels khi kênh chính lỗi):
									</span>
									<div className="flex items-center gap-2">
										{(outboundChannels as Channel[])
											.filter((ch) => ch !== step.channel && isChannelAllowed(ch))
											.map((ch) => {
												const isChecked = (step.fallback_channels || []).includes(ch);
												return (
													<button
														key={ch}
														type="button"
														onClick={() => toggleFallbackChannel(index, ch)}
														className={`px-2.5 py-1 rounded text-xs border font-medium transition-colors ${
															isChecked
																? "bg-primary/10 border-primary text-primary"
																: "bg-muted/40 border-border text-muted-foreground hover:bg-accent"
														}`}
													>
														{isChecked ? "✓ " : "+ "}
														{ch.toUpperCase()} Fallback
													</button>
												);
											})}
									</div>
								</div>
							)}

							{step.step_type === "wait" && (
								<div className="flex items-center gap-3">
									<label
										htmlFor={`wait-duration-input-${step.step_order}`}
										className="text-xs font-medium text-muted-foreground"
									>
										Thời gian chờ:
									</label>
									<input
										id={`wait-duration-input-${step.step_order}`}
										type="number"
										data-testid="wait-duration-input"
										min="1"
										step="1"
										value={Math.round((step.wait_duration_seconds || 172800) / 3600)}
										onChange={(e) =>
											handleUpdateStep(index, {
												wait_duration_seconds: Number(e.target.value) * 3600,
											})
										}
										className="w-24 px-3 py-1.5 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
									/>
									<span className="text-sm text-foreground">Giờ (Hours)</span>
									<span className="text-xs text-muted-foreground">
										(Tự động điều chỉnh theo khung giờ hợp pháp 08:00 – 21:30 VN Time)
									</span>
								</div>
							)}

							{step.step_type === "condition" && (
								<div className="space-y-2">
									<p className="text-sm text-muted-foreground">
										Kiểm tra điều kiện tương tác từ khách hàng:
									</p>
									<div className="p-3 bg-accent/40 rounded-lg text-xs space-y-1">
										<div className="font-semibold text-foreground">
											Condition: if replied then exit, else continue to next step.
										</div>
										<div className="text-muted-foreground">
											Nếu khách hàng trả lời hoặc yêu cầu dừng, chuỗi sẽ tự động dừng và cập nhật
											trạng thái CRM.
										</div>
									</div>
								</div>
							)}
						</div>
					);
				})}
			</div>

			{/* Add Step Actions */}
			<div className="flex flex-wrap items-center gap-3 pt-2">
				<button
					type="button"
					onClick={() => handleAddStep("send_email")}
					data-testid="add-step-send_email"
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-secondary text-secondary-foreground text-xs font-semibold rounded-lg border hover:bg-secondary/80 transition-colors shadow-sm"
				>
					<Plus className="w-3.5 h-3.5" aria-hidden="true" />
					Thêm bước gửi Email
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("send_zalo")}
					data-testid="add-step-send_zalo"
					disabled={!ad41Reactivated || !isChannelAllowed("zalo")}
					title={
						!ad41Reactivated
							? "Deferred — AD-41 / DEF-102"
							: !isChannelAllowed("zalo")
								? "Not enabled for this workspace"
								: undefined
					}
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-blue-500/10 text-blue-600 text-xs font-semibold rounded-lg border border-blue-500/20 hover:bg-blue-500/20 transition-colors shadow-sm disabled:opacity-50"
				>
					<Plus className="w-3.5 h-3.5" aria-hidden="true" />
					Thêm bước Zalo ZNS
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("send_telegram")}
					data-testid="add-step-send_telegram"
					disabled={!isChannelAllowed("telegram")}
					title={!isChannelAllowed("telegram") ? "Not enabled for this workspace" : undefined}
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-sky-500/10 text-sky-600 text-xs font-semibold rounded-lg border border-sky-500/20 hover:bg-sky-500/20 transition-colors shadow-sm disabled:opacity-50"
				>
					<Plus className="w-3.5 h-3.5" aria-hidden="true" />
					Thêm bước Telegram Bot
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("wait")}
					data-testid="add-step-wait"
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-secondary text-secondary-foreground text-xs font-semibold rounded-lg border hover:bg-secondary/80 transition-colors shadow-sm"
				>
					<Plus className="w-3.5 h-3.5" aria-hidden="true" />
					Thêm thời gian chờ (Wait)
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("condition")}
					data-testid="add-step-condition"
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-secondary text-secondary-foreground text-xs font-semibold rounded-lg border hover:bg-secondary/80 transition-colors shadow-sm"
				>
					<Plus className="w-3.5 h-3.5" aria-hidden="true" />
					Thêm điều kiện rẽ nhánh (Condition)
				</button>
			</div>
		</div>
	);
};

function ChannelChip({
	channel,
	allowed,
	disabledReason,
}: {
	channel: Channel;
	allowed: boolean;
	disabledReason?: string;
}) {
	const icon =
		channel === "email" ? (
			<Mail className="w-4 h-4 text-blue-500" aria-hidden="true" />
		) : channel === "zalo" ? (
			<MessageSquare className="w-4 h-4 text-blue-600" aria-hidden="true" />
		) : (
			<Send className="w-4 h-4 text-sky-500" aria-hidden="true" />
		);

	const label =
		channel === "email" ? "Email Outreach" : channel === "zalo" ? "Zalo ZNS" : "Telegram Bot";

	return (
		<div
			className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium ${
				allowed
					? "bg-emerald-500/10 border-emerald-500/20 text-emerald-600"
					: "bg-muted/40 border-border text-muted-foreground"
			}`}
			title={disabledReason}
		>
			{icon}
			{label}
			{!allowed && disabledReason && (
				<span className="text-[10px] opacity-80">— {disabledReason}</span>
			)}
		</div>
	);
}

function TemplateVariables({ onInsert }: { onInsert: (variable: string) => void }) {
	return (
		<div className="flex items-center gap-1.5" data-testid="template-variable-pills">
			<span className="text-[11px] text-muted-foreground flex items-center gap-1 mr-1">
				<Info className="w-3 h-3" aria-hidden="true" /> Chèn biến:
			</span>
			{TEMPLATE_VARIABLES.map((v) => (
				<button
					key={v.label}
					type="button"
					onClick={() => onInsert(v.label)}
					className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded border hover:bg-secondary/80 transition-colors"
					title={v.desc}
				>
					{v.label}
				</button>
			))}
		</div>
	);
}
