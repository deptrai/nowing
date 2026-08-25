"use client";

import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown, ChevronRight, ChevronUp, Code2, Trash2 } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { SchemaForm } from "@/components/schema-form/schema-form";
import { Accordion, AccordionContent, AccordionItem } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { JSONSchema } from "@/contracts/types/schema-ui.types";
import { useActionsCatalog } from "@/hooks/use-actions-catalog";
import { useWorkspaceVertical } from "@/hooks/use-workspace-vertical";
import type { BuilderTask } from "@/lib/automations/builder-schema";
import { buildDefaultValues } from "@/lib/schema-form/build-default-values";
import { Field } from "./form-field";
import { MentionTaskInput } from "./mention-task-input";

interface TaskItemProps {
	index: number;
	total: number;
	task: BuilderTask;
	workspaceId: number;
	error?: string;
	onChange: (patch: Partial<BuilderTask>) => void;
	onMoveUp: () => void;
	onMoveDown: () => void;
	onRemove: () => void;
}

function parseOptionalInt(raw: string): number | null {
	const trimmed = raw.trim();
	if (trimmed === "") return null;
	const value = Number.parseInt(trimmed, 10);
	return Number.isNaN(value) ? null : value;
}

function defaultParamsForAction(paramsSchema: JSONSchema | undefined): Record<string, unknown> {
	if (!paramsSchema) return {};
	return buildDefaultValues(paramsSchema);
}

export function TaskItem({
	index,
	total,
	task,
	workspaceId,
	error,
	onChange,
	onMoveUp,
	onMoveDown,
	onRemove,
}: TaskItemProps) {
	const { catalog, isLoading } = useActionsCatalog();
	const workspaceVertical = useWorkspaceVertical(workspaceId);
	const [rawJson, setRawJson] = useState(false);
	const rawJsonId = useId();

	const action = catalog?.find((a) => a.type === task.action);
	const paramsSchema = action?.params_schema as JSONSchema | undefined;

	const groupedOptions = useMemo(() => {
		const groups = new Map<string, { value: string; label: string }[]>();
		for (const a of catalog ?? []) {
			for (const vertical of a.verticals.length > 0 ? a.verticals : ["general"]) {
				if (!groups.has(vertical)) groups.set(vertical, []);
				groups.get(vertical)?.push({
					value: a.type,
					label: a.business_name ?? a.name,
				});
			}
		}
		const entries = Array.from(groups.entries()).map(([vertical, items]) => ({
			vertical,
			items: items.sort((a, b) => a.label.localeCompare(b.label)),
		}));
		entries.sort((a, b) => {
			if (a.vertical === workspaceVertical) return -1;
			if (b.vertical === workspaceVertical) return 1;
			return a.vertical.localeCompare(b.vertical);
		});
		return entries;
	}, [catalog, workspaceVertical]);

	function handleActionChange(value: string) {
		if (value === "agent_task") {
			onChange({ action: value, params: {}, query: "" });
		} else {
			const selected = catalog?.find((a) => a.type === value);
			onChange({
				action: value,
				params: defaultParamsForAction(selected?.params_schema as JSONSchema | undefined),
				query: "",
			});
		}
	}

	function handleParamsChange(values: Record<string, unknown>) {
		onChange({ params: values });
	}

	function handleRawJsonChange(raw: string) {
		try {
			const parsed = raw.trim() ? (JSON.parse(raw) as Record<string, unknown>) : {};
			onChange({ params: parsed });
		} catch {
			// Ignore invalid JSON while the user is typing.
		}
	}

	const rawParamsJson = useMemo(
		() => (task.params ? JSON.stringify(task.params, null, 2) : ""),
		[task.params]
	);

	return (
		<div className="rounded-md border border-border/60 bg-transparent p-3 space-y-3">
			<div className="flex items-center justify-between gap-2">
				<div className="flex items-center gap-2">
					<span className="inline-flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-foreground">
							{index + 1}
						</span>
						Task {index + 1}
					</span>
					<Select value={task.action} onValueChange={handleActionChange} disabled={isLoading}>
						<SelectTrigger className="h-7 text-xs" aria-label="Task action">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{groupedOptions.length === 0 && (
								<SelectGroup>
									<SelectLabel>Agent task</SelectLabel>
									<SelectItem value="agent_task">Agent task</SelectItem>
								</SelectGroup>
							)}
							{groupedOptions.map((group) => (
								<SelectGroup key={group.vertical}>
									<SelectLabel className="capitalize">
										{group.vertical.replace(/_/g, " ")}
									</SelectLabel>
									{group.items.map((opt) => (
										<SelectItem key={opt.value} value={opt.value}>
											{opt.label}
										</SelectItem>
									))}
								</SelectGroup>
							))}
						</SelectContent>
					</Select>
				</div>
				<div className="flex items-center gap-0.5">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground"
						disabled={index === 0}
						aria-label="Move task up"
						onClick={onMoveUp}
					>
						<ChevronUp className="h-4 w-4" aria-hidden="true" />
					</Button>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground"
						disabled={index === total - 1}
						aria-label="Move task down"
						onClick={onMoveDown}
					>
						<ChevronDown className="h-4 w-4" aria-hidden="true" />
					</Button>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-7 w-7 text-muted-foreground hover:text-destructive"
						disabled={total === 1}
						aria-label="Remove task"
						onClick={onRemove}
					>
						<Trash2 className="h-4 w-4" aria-hidden="true" />
					</Button>
				</div>
			</div>

			{error && <p className="text-xs text-destructive">{error}</p>}

			{task.action === "agent_task" ? (
				<Field hint="Type @ to reference files, folders, or connectors for extra context.">
					<MentionTaskInput
						workspaceId={workspaceId}
						value={task.query ?? ""}
						mentions={task.mentions}
						placeholder="What should the agent do? e.g. Summarize new docs in @Marketing since the last run."
						onChange={(query, mentions) => onChange({ query, mentions })}
					/>
				</Field>
			) : (
				<div className="space-y-3">
					{paramsSchema ? (
						<>
							<div className="flex items-center justify-end gap-2">
								<label
									htmlFor={rawJsonId}
									className="flex items-center gap-1.5 text-xs text-muted-foreground"
								>
									<Code2 className="h-3.5 w-3.5" aria-hidden="true" />
									<span>Raw JSON</span>
									<Switch id={rawJsonId} checked={rawJson} onCheckedChange={setRawJson} />
								</label>
							</div>
							{rawJson ? (
								<Textarea
									value={rawParamsJson}
									onChange={(e) => handleRawJsonChange(e.target.value)}
									placeholder={'{"key": "value"}'}
									rows={8}
								/>
							) : (
								<SchemaForm
									schema={paramsSchema}
									defaultValues={task.params}
									onChange={handleParamsChange}
								/>
							)}
						</>
					) : (
						<Textarea
							value={rawParamsJson}
							onChange={(e) => handleRawJsonChange(e.target.value)}
							placeholder={'{"key": "value"}'}
							rows={8}
						/>
					)}
				</div>
			)}

			<Accordion type="single" collapsible>
				<AccordionItem value="advanced" className="border-b-0">
					<AccordionPrimitive.Header className="flex">
						<AccordionPrimitive.Trigger className="group flex flex-1 items-center justify-between rounded-md py-1.5 text-left text-xs font-medium text-muted-foreground outline-none transition-all focus-visible:ring-[3px] focus-visible:ring-ring/50">
							Advanced
							<ChevronRight
								className="pointer-events-none size-4 shrink-0 transition-transform duration-200 group-data-[state=open]:rotate-90"
								aria-hidden="true"
							/>
						</AccordionPrimitive.Trigger>
					</AccordionPrimitive.Header>
					<AccordionContent className="pb-1">
						<div className="grid grid-cols-2 gap-3">
							<Field label="Max retries">
								<Input
									type="number"
									min={0}
									max={10}
									value={task.maxRetries ?? ""}
									placeholder="2 retries"
									onChange={(e) => onChange({ maxRetries: parseOptionalInt(e.target.value) })}
								/>
							</Field>
							<Field label="Timeout (seconds)">
								<Input
									type="number"
									min={1}
									value={task.timeoutSeconds ?? ""}
									placeholder="600 seconds"
									onChange={(e) => onChange({ timeoutSeconds: parseOptionalInt(e.target.value) })}
								/>
							</Field>
						</div>
					</AccordionContent>
				</AccordionItem>
			</Accordion>
		</div>
	);
}
