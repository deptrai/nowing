"use client";

import { Check, CheckCircle2, CornerDownLeft, HelpCircle, MessageSquarePlus, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { HitlDecision, InterruptResult, PerToolApprovalCard } from "../types";
import { useHitlDecision } from "../use-hitl-decision";
import { useHitlPhase } from "../use-hitl-phase";

export interface QuestionOptionItem {
	label: string;
	description?: string;
	preview?: string;
}

export function isQuestionInterrupt(result: unknown): boolean {
	if (typeof result !== "object" || result === null) return false;
	const r = result as Record<string, unknown>;
	if (r.interrupt_type === "question" || r.interrupt_type === "clarification") return true;

	const actions = r.action_requests as Array<{ name?: string }> | undefined;
	if (Array.isArray(actions) && actions.some((a) => a.name === "ask_user_question" || a.name === "prompt_clarification")) {
		return true;
	}
	return false;
}

interface QuestionApprovalCardViewProps {
	toolName: string;
	args: Record<string, unknown>;
	interruptData: InterruptResult;
	onDecision: (decision: HitlDecision) => void;
}

function QuestionApprovalCardView({
	args,
	interruptData,
	onDecision,
}: QuestionApprovalCardViewProps) {
	const { phase, setProcessing } = useHitlPhase(interruptData);

	// Extract question metadata from context or args
	const question =
		(args.question as string) ||
		(interruptData.context?.question as string) ||
		(interruptData.message as string) ||
		"Agent cần bạn cung cấp thêm thông tin để tiếp tục:";

	const header = (args.header as string) || (interruptData.context?.header as string) || "Làm rõ yêu cầu";
	const isMultiSelect = Boolean(args.multiSelect || args.multi_select || interruptData.context?.multi_select);

	// Parse options
	const rawOptions = (args.options || interruptData.context?.options || []) as Array<QuestionOptionItem | string>;
	const options: QuestionOptionItem[] = useMemo(() => {
		return rawOptions.map((opt) => {
			if (typeof opt === "string") return { label: opt };
			return opt;
		});
	}, [rawOptions]);

	const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
	const [customInput, setCustomInput] = useState("");
	const [isCustomActive, setIsCustomActive] = useState(false);

	const toggleOption = (label: string) => {
		if (phase !== "pending") return;
		if (isMultiSelect) {
			setSelectedLabels((prev) =>
				prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]
			);
		} else {
			setSelectedLabels([label]);
			setIsCustomActive(false);
		}
	};

	const handleSubmit = useCallback(() => {
		if (phase !== "pending") return;
		const finalAnswers: string[] = [...selectedLabels];
		if (isCustomActive && customInput.trim()) {
			finalAnswers.push(customInput.trim());
		}

		if (finalAnswers.length === 0 && !customInput.trim()) return;

		const answerText = finalAnswers.join(", ");
		setProcessing();
		onDecision({
			type: "approve",
			message: answerText,
			edited_action: {
				name: "ask_user_question",
				args: {
					answers: finalAnswers,
					selected_answer: answerText,
					custom_note: customInput.trim() || undefined,
				},
			},
		});
	}, [phase, selectedLabels, isCustomActive, customInput, setProcessing, onDecision]);

	// Shortcut: Enter to submit if something is selected
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Enter" && !e.shiftKey && phase === "pending" && (selectedLabels.length > 0 || customInput.trim())) {
				e.preventDefault();
				handleSubmit();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [handleSubmit, phase, selectedLabels.length, customInput]);

	const hasSelection = selectedLabels.length > 0 || (isCustomActive && customInput.trim().length > 0);

	return (
		<div className="my-4 max-w-xl overflow-hidden rounded-2xl border border-primary/20 bg-card/90 shadow-sm backdrop-blur-xs transition-all duration-300">
			{/* Header */}
			<div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-border/50 bg-muted/20">
				<div className="flex items-center gap-2">
					<div className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
						<Sparkles className="size-4" aria-hidden="true" />
					</div>
					<div>
						<div className="flex items-center gap-2">
							<Badge variant="secondary" className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5">
								{header}
							</Badge>
							{isMultiSelect && (
								<span className="text-[11px] text-muted-foreground">(Chọn nhiều phương án)</span>
							)}
						</div>
					</div>
				</div>
				{phase === "processing" ? (
					<TextShimmerLoader text="Đang xử lý..." size="sm" />
				) : phase === "complete" ? (
					<Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 text-xs gap-1">
						<Check className="size-3" /> Đã trả lời
					</Badge>
				) : null}
			</div>

			{/* Question Prompt */}
			<div className="px-5 pt-4 pb-2">
				<p className="text-sm font-medium text-foreground leading-relaxed">{question}</p>
			</div>

			{/* Options List */}
			<div className="px-5 py-3 space-y-2">
				{options.map((opt, idx) => {
					const isSelected = selectedLabels.includes(opt.label);
					return (
						<button
							key={opt.label}
							type="button"
							disabled={phase !== "pending"}
							onClick={() => toggleOption(opt.label)}
							className={cn(
								"w-full text-left rounded-xl p-3 border transition-all flex items-start gap-3 select-none",
								isSelected
									? "border-primary bg-primary/5 ring-1 ring-primary shadow-2xs"
									: "border-border/70 bg-card hover:bg-muted/40 hover:border-border",
								phase !== "pending" && "opacity-75 cursor-default"
							)}
						>
							<div
								className={cn(
									"flex size-5 shrink-0 items-center justify-center rounded-md border text-xs font-semibold mt-0.5 transition-colors",
									isSelected
										? "border-primary bg-primary text-primary-foreground"
										: "border-muted-foreground/30 text-muted-foreground bg-muted/20"
								)}
							>
								{isSelected ? <Check className="size-3.5" /> : idx + 1}
							</div>
							<div className="min-w-0 flex-1">
								<div className="text-xs font-semibold text-foreground">{opt.label}</div>
								{opt.description && (
									<div className="text-[11px] text-muted-foreground mt-0.5 leading-normal">
										{opt.description}
									</div>
								)}
							</div>
						</button>
					);
				})}

				{/* Custom option */}
				{phase === "pending" && (
					<div
						className={cn(
							"rounded-xl border p-2.5 transition-all space-y-2",
							isCustomActive
								? "border-primary/80 bg-primary/5 ring-1 ring-primary/60"
								: "border-dashed border-border/80 bg-transparent"
						)}
					>
						<button
							type="button"
							onClick={() => setIsCustomActive((v) => !v)}
							className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground font-medium select-none"
						>
							<MessageSquarePlus className="size-3.5" />
							<span>{isCustomActive ? "Nhập yêu cầu tùy chỉnh:" : "+ Nhập phương án hoặc hướng dẫn khác..."}</span>
						</button>
						{isCustomActive && (
							<Input
								autoFocus
								value={customInput}
								onChange={(e) => setCustomInput(e.target.value)}
								placeholder="Nhập ghi chú thêm cho Agent..."
								className="text-xs h-8 bg-background"
							/>
						)}
					</div>
				)}
			</div>

			{/* Footer Actions */}
			{phase === "pending" && (
				<div className="flex items-center justify-between px-5 py-3.5 border-t border-border/50 bg-muted/10">
					<span className="text-[11px] text-muted-foreground">
						{hasSelection ? "Nhấn Enter hoặc nút bên phải để xác nhận" : "Vui lòng chọn 1 phương án"}
					</span>
					<Button
						size="sm"
						disabled={!hasSelection}
						onClick={handleSubmit}
						className="gap-1.5 h-8 text-xs font-medium rounded-lg"
					>
						<span>Xác nhận</span>
						<CornerDownLeft className="size-3 opacity-70" />
					</Button>
				</div>
			)}
		</div>
	);
}

export const QuestionChoiceApproval: PerToolApprovalCard = ({ toolName, args, result }) => {
	const { dispatch } = useHitlDecision();
	return (
		<QuestionApprovalCardView
			toolName={toolName}
			args={args}
			interruptData={result}
			onDecision={(decision) => dispatch([decision])}
		/>
	);
};
