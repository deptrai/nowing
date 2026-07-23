"use client";
import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { ChevronDown, ChevronRight, ChevronUp, Trash2 } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type {
	BuilderTask,
	WriteBackAction,
	WriteBackParams,
} from "@/lib/automations/builder-schema";
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

const ACTION_OPTIONS: { value: WriteBackAction; label: string }[] = [
	{ value: "agent_task", label: "Agent task" },
	{ value: "write_back_notion", label: "Write back to Notion" },
	{ value: "write_back_linear", label: "Write back to Linear" },
	{ value: "write_back_jira", label: "Write back to Jira" },
	{ value: "write_back_slack", label: "Write back to Slack" },
];

function parseOptionalInt(raw: string): number | null {
	const trimmed = raw.trim();
	if (trimmed === "") return null;
	const value = Number.parseInt(trimmed, 10);
	return Number.isNaN(value) ? null : value;
}

function defaultWriteBackParams(action: WriteBackAction): WriteBackParams {
	switch (action) {
		case "write_back_notion":
			return {
				provider: "notion",
				title: "",
				content: null,
				parent_page_id: null,
				connector_name: null,
				object_id: null,
			};
		case "write_back_linear":
			return {
				provider: "linear",
				title: "",
				description: null,
				team_id: null,
				state: null,
				connector_name: null,
				object_id: null,
			};
		case "write_back_jira":
			return {
				provider: "jira",
				project_key: "",
				summary: "",
				description: null,
				issue_type: "Task",
				connector_name: null,
				object_id: null,
			};
		case "write_back_slack":
			return {
				provider: "slack",
				channel: "",
				text: "",
				thread_ts: null,
				connector_name: null,
				object_id: null,
			};
		default:
			// Should never happen for non write-back actions.
			return {
				provider: "notion",
				title: "",
				content: null,
				parent_page_id: null,
				connector_name: null,
				object_id: null,
			};
	}
}

function patchWriteBackParams(
	task: BuilderTask,
	patch: Partial<WriteBackParams>
): WriteBackParams | null {
	if (!task.writeBackParams) return null;
	return { ...task.writeBackParams, ...patch } as WriteBackParams;
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
	function handleActionChange(value: WriteBackAction) {
		if (value === "agent_task") {
			onChange({ action: value, writeBackParams: null, query: "" });
		} else {
			onChange({
				action: value,
				writeBackParams: defaultWriteBackParams(value),
				query: "",
			});
		}
	}

	function updateWriteBackParam(patch: Partial<WriteBackParams>) {
		const next = patchWriteBackParams(task, patch);
		if (next) onChange({ writeBackParams: next });
	}

	const params = task.writeBackParams;

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
					<Select value={task.action} onValueChange={(value) => handleActionChange(value as WriteBackAction)}>
						<SelectTrigger className="h-7 text-xs" aria-label="Task action">
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{ACTION_OPTIONS.map((opt) => (
								<SelectItem key={opt.value} value={opt.value}>
									{opt.label}
								</SelectItem>
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
						<ChevronUp className="h-4 w-4" />
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
						<ChevronDown className="h-4 w-4" />
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
						<Trash2 className="h-4 w-4" />
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
					<Field label="Connector name" hint="Optional when only one connector of this type exists.">
						<Input
							type="text"
							value={params?.connector_name ?? ""}
							aria-label="Connector name" placeholder="e.g. Acme Notion"
							onChange={(e) =>
								updateWriteBackParam({
									connector_name: e.target.value.trim() || null,
								} as Partial<WriteBackParams>)
							}
						/>
					</Field>
					{task.action === "write_back_notion" && params?.provider === "notion" && (
						<>
							<Field label="Title" required>
								<Input
									type="text"
									value={params.title}
									aria-label="Title" placeholder="Page title"
									onChange={(e) => updateWriteBackParam({ title: e.target.value } as Partial<WriteBackParams>)}
								/>
							</Field>
							<Field label="Content">
								<Input
									type="text"
									value={params.content ?? ""}
									aria-label="Content" placeholder="Page content"
									onChange={(e) =>
										updateWriteBackParam({
											content: e.target.value.trim() || null,
										} as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="Parent page id">
								<Input
									type="text"
									value={params.parent_page_id ?? ""}
									aria-label="Parent page id" placeholder="Optional parent page id"
									onChange={(e) =>
										updateWriteBackParam({
											parent_page_id: e.target.value.trim() || null,
										} as Partial<WriteBackParams>)
									}
								/>
							</Field>
						</>
					)}
					{task.action === "write_back_linear" && params?.provider === "linear" && (
						<>
							<Field label="Title" required>
								<Input
									type="text"
									value={params.title}
									aria-label="Title" placeholder="Issue title"
									onChange={(e) => updateWriteBackParam({ title: e.target.value } as Partial<WriteBackParams>)}
								/>
							</Field>
							<Field label="Description">
								<Input
									type="text"
									value={params.description ?? ""}
									aria-label="Description" placeholder="Issue description"
									onChange={(e) =>
										updateWriteBackParam({
											description: e.target.value.trim() || null,
										} as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="Team id">
								<Input
									type="text"
									value={params.team_id ?? ""}
									aria-label="Team id" placeholder="Team identifier"
									onChange={(e) =>
										updateWriteBackParam({ team_id: e.target.value.trim() || null } as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="State">
								<Input
									type="text"
									value={params.state ?? ""}
									aria-label="State" placeholder="Issue state"
									onChange={(e) =>
										updateWriteBackParam({ state: e.target.value.trim() || null } as Partial<WriteBackParams>)
									}
								/>
							</Field>
						</>
					)}
					{task.action === "write_back_jira" && params?.provider === "jira" && (
						<>
							<Field label="Project key" required>
								<Input
									type="text"
									value={params.project_key}
									aria-label="Project key" placeholder="e.g. PROJ"
									onChange={(e) =>
										updateWriteBackParam({ project_key: e.target.value } as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="Summary" required>
								<Input
									type="text"
									value={params.summary}
									aria-label="Summary" placeholder="Issue summary"
									onChange={(e) =>
										updateWriteBackParam({ summary: e.target.value } as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="Description">
								<Input
									type="text"
									value={params.description ?? ""}
									aria-label="Description" placeholder="Issue description"
									onChange={(e) =>
										updateWriteBackParam({
											description: e.target.value.trim() || null,
										} as Partial<WriteBackParams>)
									}
								/>
							</Field>
							<Field label="Issue type" required>
								<Input
									type="text"
									value={params.issue_type}
									aria-label="Issue type" placeholder="Task"
									onChange={(e) =>
										updateWriteBackParam({ issue_type: e.target.value } as Partial<WriteBackParams>)
									}
								/>
							</Field>
						</>
					)}
					{task.action === "write_back_slack" && params?.provider === "slack" && (
						<>
							<Field label="Channel" required>
								<Input
									type="text"
									value={params.channel}
									aria-label="Channel" placeholder="#daily-digest"
									onChange={(e) => updateWriteBackParam({ channel: e.target.value } as Partial<WriteBackParams>)}
								/>
							</Field>
							<Field label="Message text" required>
								<Input
									type="text"
									value={params.text}
									aria-label="Message text" placeholder="What to send"
									onChange={(e) => updateWriteBackParam({ text: e.target.value } as Partial<WriteBackParams>)}
								/>
							</Field>
							<Field label="Thread ts">
								<Input
									type="text"
									value={params.thread_ts ?? ""}
									aria-label="Thread ts" placeholder="Optional thread timestamp"
									onChange={(e) =>
										updateWriteBackParam({
											thread_ts: e.target.value.trim() || null,
										} as Partial<WriteBackParams>)
									}
								/>
							</Field>
						</>
					)}
					<Field label="Existing object id" hint="Optional: update instead of create.">
						<Input
							type="text"
							value={params?.object_id ?? ""}
							aria-label="Existing object id" placeholder="page id / issue key / message ts"
							onChange={(e) =>
								updateWriteBackParam({
									object_id: e.target.value.trim() || null,
								} as Partial<WriteBackParams>)
							}
						/>
					</Field>
				</div>
			)}

			<Accordion type="single" collapsible>
				<AccordionItem value="advanced" className="border-b-0">
					<AccordionPrimitive.Header className="flex">
						<AccordionPrimitive.Trigger className="group flex flex-1 items-center justify-between rounded-md py-1.5 text-left text-xs font-medium text-muted-foreground outline-none transition-all focus-visible:ring-[3px] focus-visible:ring-ring/50">
							Advanced
							<ChevronRight className="pointer-events-none size-4 shrink-0 transition-transform duration-200 group-data-[state=open]:rotate-90" />
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
