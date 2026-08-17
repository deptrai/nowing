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
	Trash2,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import type { SequenceCreate, SequenceStep } from "../../contracts/types/sequence.types";

interface VisualCadenceBuilderProps {
	workspaceId?: number | string;
	initialSequence?: Partial<SequenceCreate>;
	onSave: (payload: SequenceCreate) => Promise<void>;
	isSaving?: boolean;
}

const TEMPLATE_VARIABLES = [
	{ label: "{customer_name}", desc: "Tên khách hàng / liên hệ" },
	{ label: "{company}", desc: "Tên công ty / doanh nghiệp" },
	{ label: "{property_title}", desc: "Tiêu đề BĐS / bài đăng" },
	{ label: "{consultant_phone}", desc: "Hotline chuyên viên" },
];

export const VisualCadenceBuilder: React.FC<VisualCadenceBuilderProps> = ({
	initialSequence,
	onSave,
	isSaving = false,
}) => {
	const [name, setName] = useState(initialSequence?.name || "Chiến dịch tiếp cận tự động");
	const [description, setDescription] = useState(initialSequence?.description || "");
	const [selectedChannel, setSelectedChannel] = useState<string>("email");

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
				condition_config: {},
				is_enabled: true,
			},
		]
	);

	const handleAddStep = (type: "send_email" | "wait" | "condition") => {
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

	const insertVariable = (index: number, variable: string) => {
		const currentStep = steps[index];
		const currentBody = currentStep.template?.body || "";
		handleUpdateStep(index, {
			template: {
				...currentStep.template,
				body: `${currentBody} ${variable}`,
			},
		});
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		const payload: SequenceCreate = {
			name,
			description,
			status: "active",
			shared: false,
			entry_step_order: 1,
			steps,
		};
		await onSave(payload);
	};

	return (
		<div className="space-y-6" data-testid="sequence-cadence-builder">
			{/* Top Header Card */}
			<div className="bg-card border rounded-xl p-6 shadow-sm space-y-4">
				<div className="flex items-center justify-between">
					<div>
						<h2 className="text-xl font-semibold text-foreground">
							Visual Cadence Sequence Builder
						</h2>
						<p className="text-sm text-muted-foreground">
							Thiết lập quy trình tiếp cận khách hàng tự động đa bước (Tuân thủ khung giờ 08:00 -
							21:30 VN Time)
						</p>
					</div>
					<button
						type="button"
						onClick={handleSubmit}
						disabled={isSaving || steps.length === 0}
						data-testid="save-sequence-btn"
						className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
					>
						<Save className="w-4 h-4" />
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
							placeholder="VD: Gửi chuỗi 3 email theo dõi phản hồi với khoảng cách 48h"
							className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none"
						/>
					</div>
				</div>

				{/* Outbound Channel Selector (AD-41 Gate) */}
				<div className="pt-2">
					<span className="block text-xs font-semibold text-foreground uppercase tracking-wider mb-2">
						Kênh tiếp cận chính (Outbound Channel)
					</span>
					<div className="flex flex-wrap gap-3">
						<button
							type="button"
							data-testid="channel-option-email"
							onClick={() => setSelectedChannel("email")}
							className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
								selectedChannel === "email"
									? "bg-primary/10 border-primary text-primary"
									: "bg-background border-border text-foreground hover:bg-accent"
							}`}
						>
							<Mail className="w-4 h-4" />
							Email Outreach (Sẵn sàng)
						</button>

						<button
							type="button"
							data-testid="channel-option-zalo"
							data-deferred="true"
							disabled
							className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-border bg-muted/40 text-muted-foreground text-sm cursor-not-allowed opacity-60"
							title="Zalo ZNS Outreach tạm hoãn đến Sprint 3 (AD-41 / DEF-102)"
						>
							<MessageSquare className="w-4 h-4" />
							Zalo ZNS (Deferred)
						</button>

						<button
							type="button"
							data-testid="channel-option-telegram"
							data-deferred="true"
							disabled
							className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-dashed border-border bg-muted/40 text-muted-foreground text-sm cursor-not-allowed opacity-60"
							title="Telegram Outreach tạm hoãn (AD-41)"
						>
							<Send className="w-4 h-4" />
							Telegram (Deferred)
						</button>
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
												<Mail className="w-4 h-4 text-blue-500" />
												Bước gửi Email
											</>
										)}
										{step.step_type === "wait" && (
											<>
												<Clock className="w-4 h-4 text-amber-500" />
												Thời gian chờ (Wait / Delay)
											</>
										)}
										{step.step_type === "condition" && (
											<>
												<GitBranch className="w-4 h-4 text-purple-500" />
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
										<Trash2 className="w-4 h-4" />
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
											value={step.template?.subject || ""}
											onChange={(e) =>
												handleUpdateStep(index, {
													template: {
														...step.template,
														subject: e.target.value,
													},
												})
											}
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
											{/* Dynamic Template Variable Pills */}
											<div
												className="flex items-center gap-1.5"
												data-testid="template-variable-pills"
											>
												<span className="text-[11px] text-muted-foreground flex items-center gap-1 mr-1">
													<Info className="w-3 h-3" /> Chèn biến:
												</span>
												{TEMPLATE_VARIABLES.map((v) => (
													<button
														key={v.label}
														type="button"
														onClick={() => insertVariable(index, v.label)}
														className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded border hover:bg-secondary/80 transition-colors"
														title={v.desc}
													>
														{v.label}
													</button>
												))}
											</div>
										</div>
										<textarea
											id={`email-body-input-${step.step_order}`}
											rows={4}
											value={step.template?.body || ""}
											onChange={(e) =>
												handleUpdateStep(index, {
													template: {
														...step.template,
														body: e.target.value,
													},
												})
											}
											className="w-full px-3 py-2 border rounded-lg bg-background text-foreground text-sm focus:ring-2 focus:ring-primary focus:outline-none font-mono text-xs"
										/>
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
										min="60"
										step="60"
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
					<Plus className="w-3.5 h-3.5" />
					Thêm bước gửi Email
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("wait")}
					data-testid="add-step-wait"
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-secondary text-secondary-foreground text-xs font-semibold rounded-lg border hover:bg-secondary/80 transition-colors shadow-sm"
				>
					<Plus className="w-3.5 h-3.5" />
					Thêm thời gian chờ (Wait)
				</button>

				<button
					type="button"
					onClick={() => handleAddStep("condition")}
					data-testid="add-step-condition"
					className="inline-flex items-center gap-1.5 px-3 py-2 bg-secondary text-secondary-foreground text-xs font-semibold rounded-lg border hover:bg-secondary/80 transition-colors shadow-sm"
				>
					<Plus className="w-3.5 h-3.5" />
					Thêm điều kiện rẽ nhánh (Condition)
				</button>
			</div>
		</div>
	);
};
