"use client";

import { Check, ChevronRight, Copy, RotateCcw, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getToolDisplayName, getToolIcon } from "@/contracts/enums/toolIcons";
import { type AgentAction, agentActionsApiService } from "@/lib/apis/agent-actions-api.service";
import { AppError } from "@/lib/error";
import { formatRelativeDate } from "@/lib/format-date";
import { cn } from "@/lib/utils";

interface ActionLogItemProps {
	action: AgentAction;
	threadId: number;
	onRevertSuccess: () => void;
}

function formatPrimitiveValue(value: unknown) {
	if (value === null) return "null";
	if (value === undefined) return "undefined";
	if (typeof value === "string") return value;
	if (typeof value === "number" || typeof value === "boolean") return String(value);
	return JSON.stringify(value, null, 2);
}

function ArgumentValue({ value }: { value: unknown }) {
	const formatted = formatPrimitiveValue(value);
	const isBlockValue =
		typeof value === "object" ||
		(typeof value === "string" && (value.includes("\n") || value.length > 120));

	if (isBlockValue) {
		return (
			<pre className="mt-2 whitespace-pre-wrap break-words bg-popover px-4 py-3 text-[11px] leading-relaxed text-popover-foreground/80">
				{formatted}
			</pre>
		);
	}

	return (
		<p className="mt-1 break-words font-mono text-[11px] leading-relaxed text-popover-foreground/80">
			{formatted}
		</p>
	);
}

function StructuredArguments({ args }: { args: Record<string, unknown> }) {
	return (
		<div className="divide-y divide-popover-border border-t border-popover-border">
			{Object.entries(args).map(([key, value]) => (
				<div key={key} className="bg-popover">
					<div className="px-4 py-3">
						<p className="font-mono text-[10px] font-medium text-muted-foreground">{key}</p>
						<ArgumentValue value={value} />
					</div>
				</div>
			))}
		</div>
	);
}

export function ActionLogItem({ action, threadId, onRevertSuccess }: ActionLogItemProps) {
	const t = useTranslations("actionLog");
	const tCommon = useTranslations("common");
	const [isExpanded, setIsExpanded] = useState(false);
	const [isReverting, setIsReverting] = useState(false);
	const [confirmOpen, setConfirmOpen] = useState(false);
	const [copiedSection, setCopiedSection] = useState<"arguments" | null>(null);

	const isAlreadyReverted = action.reverted_by_action_id !== null;
	const isRevertAction = action.is_revert_action;
	const hasError = action.error !== null && action.error !== undefined;

	const Icon = getToolIcon(action.tool_name);
	const displayName = getToolDisplayName(action.tool_name);

	const argsPreview = action.args ? JSON.stringify(action.args, null, 2) : null;

	const canRevert = action.reversible && !isAlreadyReverted && !isRevertAction && !hasError;

	const handleCopyArguments = async () => {
		if (!argsPreview) return;

		try {
			await navigator.clipboard.writeText(argsPreview);
			setCopiedSection("arguments");
			toast.success(t("copy_args_success"));
			window.setTimeout(() => setCopiedSection(null), 1200);
		} catch {
			toast.error(t("copy_args_failed"));
		}
	};

	const handleRevert = async () => {
		setIsReverting(true);
		try {
			const response = await agentActionsApiService.revert(threadId, action.id);
			toast.success(response.message || t("revert_success"));
			onRevertSuccess();
		} catch (err) {
			const message =
				err instanceof AppError
					? err.message
					: err instanceof Error
						? err.message
						: t("revert_failed");
			toast.error(message);
		} finally {
			setIsReverting(false);
			setConfirmOpen(false);
		}
	};

	return (
		<div
			className={cn(
				"overflow-hidden rounded-lg border border-popover-border bg-popover text-popover-foreground transition-colors",
				isAlreadyReverted && "opacity-70"
			)}
		>
			<Button
				type="button"
				variant="ghost"
				onClick={() => setIsExpanded((v) => !v)}
				className="h-auto w-full items-start justify-start gap-3 rounded-none p-3 text-left hover:bg-accent hover:text-accent-foreground"
				aria-expanded={isExpanded}
			>
				<div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent">
					{isRevertAction ? (
						<Undo2 className="size-4 text-muted-foreground" aria-hidden="true" />
					) : (
						<Icon className="size-4 text-muted-foreground" aria-hidden="true" />
					)}
				</div>
				<div className="flex min-w-0 flex-1 flex-col gap-1">
					<div className="flex flex-wrap items-center gap-1.5">
						<span className="truncate text-sm font-medium">{displayName}</span>
						{isRevertAction && (
							<Badge variant="secondary" className="text-[10px]">
								{t("revert_badge")}
							</Badge>
						)}
						{hasError && (
							<Badge variant="destructive" className="text-[10px]">
								{t("error_badge")}
							</Badge>
						)}
						{!isRevertAction && action.reversible && !isAlreadyReverted && (
							<Badge
								variant="secondary"
								className="border-0 bg-neutral-200 px-1.5 py-0.5 text-[10px] text-neutral-700 dark:bg-neutral-700 dark:text-neutral-200"
							>
								{t("reversible_badge")}
							</Badge>
						)}
						{isAlreadyReverted && (
							<Badge variant="secondary" className="text-[10px]">
								{t("reverted_badge")}
							</Badge>
						)}
					</div>
					<p className="text-xs text-muted-foreground">{formatRelativeDate(action.created_at)}</p>
				</div>
				<ChevronRight
					className={cn(
						"size-4 shrink-0 self-center text-muted-foreground transition-transform",
						isExpanded && "rotate-90"
					)}
				/>
			</Button>

			{isExpanded && (
				<div className="flex flex-col border-t border-popover-border bg-accent/80">
					{action.args && argsPreview && (
						<div className="border-b border-popover-border">
							<div className="flex items-center justify-between px-4 py-2">
								<p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
									{t("arguments_label")}
								</p>
								<Button
									type="button"
									size="sm"
									variant="ghost"
									onClick={handleCopyArguments}
									className="size-6 rounded-lg p-0 text-muted-foreground hover:bg-popover hover:text-popover-foreground"
									aria-label={copiedSection === "arguments" ? t("args_copied_aria") : t("copy_args_aria")}
								>
									{copiedSection === "arguments" ? (
										<Check className="size-3" aria-hidden="true" />
									) : (
										<Copy className="size-3" aria-hidden="true" />
									)}
								</Button>
							</div>
							<StructuredArguments args={action.args} />
						</div>
					)}
					{action.error && (
						<div className="border-b border-popover-border">
							<p className="px-4 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								{t("error_label")}
							</p>
							<pre className="max-h-32 overflow-auto border-t border-popover-border bg-destructive/10 px-4 py-3 text-[11px] text-destructive">
								{JSON.stringify(action.error, null, 2)}
							</pre>
						</div>
					)}
					{action.reverse_descriptor && (
						<div className="border-b border-popover-border">
							<p className="px-4 py-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
								{t("reverse_plan_label")}
							</p>
							<pre className="max-h-32 overflow-auto border-t border-popover-border bg-popover px-4 py-3 text-[11px] text-popover-foreground/80">
								{JSON.stringify(action.reverse_descriptor, null, 2)}
							</pre>
						</div>
					)}

					<div className="flex items-center justify-between px-4 py-3">
						<p className="text-[10px] text-muted-foreground">
							{t("action_id_label")} <span className="font-mono">{action.id}</span>
						</p>
						{canRevert ? (
							<AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
								<AlertDialogTrigger asChild>
									<Button size="sm" variant="secondary" className="gap-1.5">
										<RotateCcw className="size-3.5" aria-hidden="true" />
										Revert
									</Button>
								</AlertDialogTrigger>
								<AlertDialogContent>
									<AlertDialogHeader>
										<AlertDialogTitle>{t("revert_confirm_title")}</AlertDialogTitle>
										<AlertDialogDescription>
											This will undo <span className="font-medium">{displayName}</span> and append a
											new audit entry. The agent's chat history is preserved — only the tool's
											effects on your knowledge base or connectors will be reversed where possible.
										</AlertDialogDescription>
									</AlertDialogHeader>
									<AlertDialogFooter>
										<AlertDialogCancel disabled={isReverting}>{tCommon("cancel")}</AlertDialogCancel>
										<AlertDialogAction
											onClick={(e) => {
												e.preventDefault();
												handleRevert();
											}}
											disabled={isReverting}
											className="bg-secondary text-secondary-foreground hover:bg-secondary/80 focus-visible:ring-0"
										>
											{isReverting ? t("revert_confirm_reverting") : t("revert_btn")}
										</AlertDialogAction>
									</AlertDialogFooter>
								</AlertDialogContent>
							</AlertDialog>
						) : (
							<div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
								{isAlreadyReverted
									? t("already_reverted")
									: isRevertAction
										? t("revert_entry")
										: hasError
											? t("cannot_revert_error")
											: t("not_reversible")}
							</div>
						)}
					</div>
				</div>
			)}
		</div>
	);
}
