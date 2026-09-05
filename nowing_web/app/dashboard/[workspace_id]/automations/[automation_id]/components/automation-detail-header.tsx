"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { ArrowLeft, BookOpen, Pause, Pencil, Play, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { updateAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { createPlaybookMutationAtom } from "@/atoms/playbooks/playbooks-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import type { Automation } from "@/contracts/types/automation.types";
import type { WorkspaceVertical } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { DeleteAutomationDialog } from "../../components/delete-automation-dialog";

const PLAYBOOK_VERTICALS: WorkspaceVertical[] = ["general", "real_estate", "auto", "b2b_equipment"];

interface AutomationDetailHeaderProps {
	automation: Automation;
	workspaceId: number;
	canUpdate: boolean;
	canDelete: boolean;
}

function defaultVerticals(vertical: WorkspaceVertical | undefined): WorkspaceVertical[] {
	if (!vertical || vertical === "general") {
		return ["general"];
	}
	return [vertical, "general"];
}

/**
 * Title bar for the detail page: back link, name, status badge,
 * description, and the two destructive-ish primary actions (pause /
 * resume + delete). Same mutation atoms as the list-row actions to
 * keep caches coherent.
 *
 * Archived automations hide the pause/resume toggle (we don't unarchive
 * here — that flow comes later if we need it).
 */
export function AutomationDetailHeader({
	automation,
	workspaceId,
	canUpdate,
	canDelete,
}: AutomationDetailHeaderProps) {
	const router = useRouter();
	const { mutateAsync: updateAutomation, isPending: updating } = useAtomValue(
		updateAutomationMutationAtom
	);
	const { mutateAsync: createPlaybook, isPending: savingPlaybook } = useAtomValue(
		createPlaybookMutationAtom
	);
	const [deleteOpen, setDeleteOpen] = useState(false);
	const [saveDialogOpen, setSaveDialogOpen] = useState(false);

	const { data: workspace } = useQuery({
		queryKey: cacheKeys.workspaces.detail(String(workspaceId)),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	const workspaceVertical = workspace?.vertical;

	const [playbookName, setPlaybookName] = useState(`${automation.name} (playbook)`);
	const [playbookDescription, setPlaybookDescription] = useState(automation.description ?? "");
	const [selectedVerticals, setSelectedVerticals] = useState<WorkspaceVertical[]>(() =>
		defaultVerticals(workspaceVertical)
	);

	// Keep default verticals in sync once the workspace is loaded.
	const targetDefaults = useMemo(() => defaultVerticals(workspaceVertical), [workspaceVertical]);

	const canToggle = canUpdate && automation.status !== "archived";
	const nextStatus = automation.status === "active" ? "paused" : "active";
	const pauseLabel = automation.status === "active" ? "Pause" : "Resume";
	const PauseIcon = automation.status === "active" ? Pause : Play;

	const handleDeleted = useCallback(() => {
		router.push(`/dashboard/${workspaceId}/automations`);
	}, [router, workspaceId]);

	async function handleTogglePause() {
		await updateAutomation({
			automationId: automation.id,
			patch: { status: nextStatus },
		});
	}

	function openSaveDialog() {
		setPlaybookName(`${automation.name} (playbook)`);
		setPlaybookDescription(automation.description ?? "");
		setSelectedVerticals(targetDefaults);
		setSaveDialogOpen(true);
	}

	function toggleVertical(vertical: WorkspaceVertical) {
		setSelectedVerticals((prev) =>
			prev.includes(vertical) ? prev.filter((v) => v !== vertical) : [...prev, vertical]
		);
	}

	async function handleSaveAsPlaybook() {
		const name = playbookName.trim();
		if (!name) return;
		await createPlaybook({
			source_automation_id: automation.id,
			name,
			description: playbookDescription.trim() || null,
			tool_scope: [],
			verticals: selectedVerticals,
		});
		setSaveDialogOpen(false);
	}

	return (
		<>
			<div className="space-y-3">
				<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
					<Link
						href={`/dashboard/${workspaceId}/automations`}
						className="text-xs text-muted-foreground"
					>
						<ArrowLeft className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
						Back to automations
					</Link>
				</Button>

				<div className="flex items-start justify-between gap-4 flex-wrap">
					<div className="space-y-2 min-w-0 flex-1">
						<h1
							data-testid="automation-detail-name"
							className="font-serif text-2xl sm:text-3xl font-normal text-foreground break-words"
						>
							{automation.name}
						</h1>
						{automation.description && (
							<p className="text-xs sm:text-sm text-muted-foreground max-w-3xl font-sans">
								{automation.description}
							</p>
						)}
					</div>

					<div className="flex items-center gap-2 shrink-0">
						{canUpdate && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								disabled={savingPlaybook}
								onClick={openSaveDialog}
								className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<BookOpen className="mr-1 h-4 w-4" aria-hidden="true" />
								Save as Playbook
							</Button>
						)}
						{canUpdate && (
							<Button
								asChild
								type="button"
								variant="ghost"
								size="sm"
								className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<Link href={`/dashboard/${workspaceId}/automations/${automation.id}/edit`}>
									<Pencil className="mr-1 h-4 w-4" aria-hidden="true" />
									Edit
								</Link>
							</Button>
						)}
						{canToggle && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={handleTogglePause}
								disabled={updating}
								className="relative justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<span
									className={
										updating
											? "inline-flex items-center whitespace-nowrap opacity-0"
											: "inline-flex items-center whitespace-nowrap"
									}
								>
									<PauseIcon className="mr-1 h-4 w-4" aria-hidden="true" />
									{pauseLabel}
								</span>
								{updating && (
									<Spinner
										size="xs"
										className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
									/>
								)}
							</Button>
						)}
						{canDelete && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={() => setDeleteOpen(true)}
								className="justify-start rounded-md bg-muted px-3 hover:bg-accent"
							>
								<Trash2 className="mr-1 h-4 w-4" aria-hidden="true" />
								Delete
							</Button>
						)}
					</div>
				</div>
			</div>

			<Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>Save as Playbook</DialogTitle>
						<DialogDescription>Create a reusable template from this automation.</DialogDescription>
					</DialogHeader>
					<div className="space-y-4 py-2">
						<div className="space-y-2">
							<Label htmlFor="playbook-name">Name</Label>
							<Input
								id="playbook-name"
								value={playbookName}
								onChange={(e) => setPlaybookName(e.target.value)}
								placeholder="Playbook name"
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="playbook-description">Description</Label>
							<Input
								id="playbook-description"
								value={playbookDescription}
								onChange={(e) => setPlaybookDescription(e.target.value)}
								placeholder="Optional description"
							/>
						</div>
						<div className="space-y-2">
							<Label>Verticals</Label>
							<p className="text-xs text-muted-foreground">
								Tag the industries this playbook applies to.
							</p>
							<div className="flex flex-wrap gap-3 pt-1">
								{PLAYBOOK_VERTICALS.map((vertical) => {
									const verticalId = `playbook-vertical-${vertical}`;
									return (
										<label
											htmlFor={verticalId}
											key={vertical}
											className="flex items-center gap-2 text-sm"
										>
											<Checkbox
												id={verticalId}
												checked={selectedVerticals.includes(vertical)}
												onCheckedChange={() => toggleVertical(vertical)}
											/>
											{vertical.replace(/_/g, " ")}
										</label>
									);
								})}
							</div>
						</div>
					</div>
					<DialogFooter>
						<Button
							type="button"
							variant="outline"
							onClick={() => setSaveDialogOpen(false)}
							disabled={savingPlaybook}
						>
							Cancel
						</Button>
						<Button
							type="button"
							disabled={!playbookName.trim() || savingPlaybook || selectedVerticals.length === 0}
							onClick={handleSaveAsPlaybook}
						>
							{savingPlaybook ? <Spinner size="sm" /> : "Save Playbook"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{canDelete && (
				<DeleteAutomationDialog
					open={deleteOpen}
					onOpenChange={setDeleteOpen}
					automationId={automation.id}
					automationName={automation.name}
					workspaceId={workspaceId}
					onDeleted={handleDeleted}
				/>
			)}
		</>
	);
}
