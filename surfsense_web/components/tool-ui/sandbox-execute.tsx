"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
	AlertCircleIcon,
	CheckCircle2Icon,
	ChevronRightIcon,
	Loader2Icon,
	TerminalIcon,
	XCircleIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

// ============================================================================
// Zod Schemas
// ============================================================================

const ExecuteArgsSchema = z.object({
	command: z.string(),
	timeout: z.number().nullish(),
});

const ExecuteResultSchema = z.object({
	result: z.string().nullish(),
	exit_code: z.number().nullish(),
	output: z.string().nullish(),
	error: z.string().nullish(),
	status: z.string().nullish(),
});

// ============================================================================
// Types
// ============================================================================

type ExecuteArgs = z.infer<typeof ExecuteArgsSchema>;
type ExecuteResult = z.infer<typeof ExecuteResultSchema>;

interface ParsedOutput {
	exitCode: number | null;
	output: string;
	truncated: boolean;
	isError: boolean;
}

// ============================================================================
// Helpers
// ============================================================================

function parseExecuteResult(result: ExecuteResult): ParsedOutput {
	const raw = result.result || result.output || "";

	if (result.error) {
		return { exitCode: null, output: result.error, truncated: false, isError: true };
	}

	if (result.exit_code !== undefined && result.exit_code !== null) {
		return {
			exitCode: result.exit_code,
			output: raw,
			truncated: raw.includes("[Output was truncated"),
			isError: result.exit_code !== 0,
		};
	}

	const exitMatch = raw.match(/^Exit code:\s*(\d+)/);
	if (exitMatch) {
		const exitCode = parseInt(exitMatch[1], 10);
		const outputMatch = raw.match(/\nOutput:\n([\s\S]*)/);
		const output = outputMatch ? outputMatch[1] : "";
		return {
			exitCode,
			output,
			truncated: raw.includes("[Output was truncated"),
			isError: exitCode !== 0,
		};
	}

	if (raw.startsWith("Error:")) {
		return { exitCode: null, output: raw, truncated: false, isError: true };
	}

	return { exitCode: null, output: raw, truncated: false, isError: false };
}

function truncateCommand(command: string, maxLen = 80): string {
	if (command.length <= maxLen) return command;
	return command.slice(0, maxLen) + "…";
}

// ============================================================================
// Sub-Components
// ============================================================================

function ExecuteLoading({ command }: { command: string }) {
	return (
		<div className="my-4 flex max-w-lg items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
			<Loader2Icon className="size-4 shrink-0 animate-spin text-muted-foreground" />
			<code className="truncate text-sm text-muted-foreground font-mono">
				{truncateCommand(command)}
			</code>
		</div>
	);
}

function ExecuteErrorState({ command, error }: { command: string; error: string }) {
	return (
		<div className="my-4 max-w-lg overflow-hidden rounded-xl border border-destructive/20 bg-destructive/5 p-4">
			<div className="flex items-center gap-3">
				<div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
					<AlertCircleIcon className="size-4 text-destructive" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-medium text-destructive">Execution failed</p>
					<code className="mt-0.5 block truncate text-xs text-muted-foreground font-mono">
						$ {command}
					</code>
					<p className="mt-1 text-xs text-muted-foreground">{error}</p>
				</div>
			</div>
		</div>
	);
}

function ExecuteCancelledState({ command }: { command: string }) {
	return (
		<div className="my-4 max-w-lg rounded-xl border border-muted p-4 text-muted-foreground">
			<p className="flex items-center gap-2 font-mono text-sm">
				<TerminalIcon className="size-4" />
				<span className="line-through truncate">$ {command}</span>
			</p>
		</div>
	);
}

function ExecuteResult({
	command,
	parsed,
}: {
	command: string;
	parsed: ParsedOutput;
}) {
	const [open, setOpen] = useState(false);
	const hasOutput = parsed.output.trim().length > 0;

	const exitBadge = useMemo(() => {
		if (parsed.exitCode === null) return null;
		const success = parsed.exitCode === 0;
		return (
			<Badge
				variant={success ? "secondary" : "destructive"}
				className={cn(
					"ml-auto gap-1 text-[10px] px-1.5 py-0",
					success && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
				)}
			>
				{success ? (
					<CheckCircle2Icon className="size-3" />
				) : (
					<XCircleIcon className="size-3" />
				)}
				{parsed.exitCode}
			</Badge>
		);
	}, [parsed.exitCode]);

	return (
		<div className="my-4 max-w-lg">
			<Collapsible open={open} onOpenChange={setOpen}>
				<CollapsibleTrigger
					className={cn(
						"flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left transition-colors hover:bg-accent/50",
						open && "rounded-b-none border-b-0",
						parsed.isError && "border-destructive/20"
					)}
					disabled={!hasOutput}
				>
					<ChevronRightIcon
						className={cn(
							"size-3.5 shrink-0 text-muted-foreground transition-transform duration-200",
							open && "rotate-90",
							!hasOutput && "invisible"
						)}
					/>
					<TerminalIcon className="size-3.5 shrink-0 text-muted-foreground" />
					<code className="min-w-0 flex-1 truncate text-sm font-mono">
						{truncateCommand(command)}
					</code>
					{exitBadge}
				</CollapsibleTrigger>

				<CollapsibleContent>
					<div
						className={cn(
							"rounded-b-xl border border-t-0 bg-zinc-950 dark:bg-zinc-900/60 px-4 py-3",
							parsed.isError && "border-destructive/20"
						)}
					>
						<pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs font-mono text-zinc-300 leading-relaxed">
							{parsed.output}
						</pre>
						{parsed.truncated && (
							<p className="mt-2 text-[10px] text-zinc-500 italic">
								Output was truncated due to size limits
							</p>
						)}
					</div>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
}

// ============================================================================
// Tool UI
// ============================================================================

export const SandboxExecuteToolUI = makeAssistantToolUI<ExecuteArgs, ExecuteResult>({
	toolName: "execute",
	render: function SandboxExecuteUI({ args, result, status }) {
		const command = args.command || "…";

		if (status.type === "running" || status.type === "requires-action") {
			return <ExecuteLoading command={command} />;
		}

		if (status.type === "incomplete") {
			if (status.reason === "cancelled") {
				return <ExecuteCancelledState command={command} />;
			}
			if (status.reason === "error") {
				return (
					<ExecuteErrorState
						command={command}
						error={typeof status.error === "string" ? status.error : "An error occurred"}
					/>
				);
			}
		}

		if (!result) {
			return <ExecuteLoading command={command} />;
		}

		if (result.error && !result.result && !result.output) {
			return <ExecuteErrorState command={command} error={result.error} />;
		}

		const parsed = parseExecuteResult(result);
		return <ExecuteResult command={command} parsed={parsed} />;
	},
});

export {
	ExecuteArgsSchema,
	ExecuteResultSchema,
	type ExecuteArgs,
	type ExecuteResult,
};
