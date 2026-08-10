"use client";

import { useAtom } from "jotai";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
	AdminAgentConfigCreateRequest,
	AdminAgentConfigRead,
	AdminAgentConfigUpdateRequest,
} from "@/contracts/types/admin-agent-registry.types";
import { adminAgentRegistryApiService } from "@/lib/apis/admin-agent-registry-api.service";

const emptyDraft: AdminAgentConfigCreateRequest = {
	client_id: "",
	name: "",
	display_name: "",
	slug: "",
	system_instructions: "",
	enabled_tools: [],
	disabled_tools: [],
	model_name: "",
	citations_enabled: true,
	is_active: true,
};

function toolStringToArray(value: string): string[] {
	return value
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean);
}

function toolArrayToString(value: string[]): string {
	return value.join(", ");
}

export default function AgentRegistryAdminPage() {
	const [{ data: user, isLoading: userLoading }] = useAtom(currentUserAtom);
	const [agents, setAgents] = useState<AdminAgentConfigRead[]>([]);
	const [loading, setLoading] = useState(false);
	const [filterClientId, setFilterClientId] = useState("");

	const [createOpen, setCreateOpen] = useState(false);
	const [editAgent, setEditAgent] = useState<AdminAgentConfigRead | null>(null);
	const [draft, setDraft] = useState<AdminAgentConfigCreateRequest & { id?: string }>(emptyDraft);
	const [isSubmitting, setIsSubmitting] = useState(false);

	const loadAgents = useCallback(async (clientId?: string) => {
		setLoading(true);
		try {
			const data = await adminAgentRegistryApiService.listAgents(clientId);
			setAgents(data);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Failed to load agents");
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		if (user?.is_superuser) {
			void loadAgents();
		}
	}, [user, loadAgents]);

	const filteredAgents = useMemo(() => {
		if (!filterClientId.trim()) return agents;
		return agents.filter((a) => a.client_id.toLowerCase().includes(filterClientId.toLowerCase()));
	}, [agents, filterClientId]);

	function openCreate() {
		setDraft(emptyDraft);
		setEditAgent(null);
		setCreateOpen(true);
	}

	function openEdit(agent: AdminAgentConfigRead) {
		setEditAgent(agent);
		setDraft({
			id: agent.id,
			client_id: agent.client_id,
			name: agent.name,
			display_name: agent.display_name,
			slug: agent.slug,
			system_instructions: agent.system_instructions ?? "",
			enabled_tools: agent.enabled_tools,
			disabled_tools: agent.disabled_tools,
			model_name: agent.model_name ?? "",
			citations_enabled: agent.citations_enabled,
			is_active: agent.is_active,
		});
		setCreateOpen(true);
	}

	function closeDialog() {
		setCreateOpen(false);
		setDraft(emptyDraft);
		setEditAgent(null);
	}

	async function handleSave() {
		if (!draft.client_id.trim() || !draft.name.trim() || !draft.display_name.trim()) {
			toast.error("Client ID, name, and display name are required");
			return;
		}

		const { id: _id, client_id: rawClientId, ...base } = draft;
		const client_id = rawClientId.trim();
		const createPayload: AdminAgentConfigCreateRequest = {
			client_id,
			name: base.name.trim(),
			display_name: base.display_name.trim(),
			slug: base.slug.trim(),
			system_instructions: base.system_instructions?.trim() || null,
			enabled_tools: base.enabled_tools,
			disabled_tools: base.disabled_tools,
			model_name: base.model_name?.trim() || null,
			citations_enabled: base.citations_enabled,
			is_active: base.is_active,
		};

		setIsSubmitting(true);
		try {
			if (editAgent) {
				const update: AdminAgentConfigUpdateRequest = base;
				await adminAgentRegistryApiService.updateAgent(editAgent.id, update);
				toast.success("Agent updated");
			} else {
				await adminAgentRegistryApiService.createAgent(createPayload);
				toast.success("Agent created");
			}
			closeDialog();
			await loadAgents(filterClientId || undefined);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Failed to save agent");
		} finally {
			setIsSubmitting(false);
		}
	}

	async function handleDelete(agent: AdminAgentConfigRead) {
		if (!confirm(`Deactivate agent "${agent.display_name}"?`)) return;
		try {
			await adminAgentRegistryApiService.deleteAgent(agent.id);
			toast.success("Agent deactivated");
			await loadAgents(filterClientId || undefined);
		} catch (error) {
			toast.error(error instanceof Error ? error.message : "Failed to deactivate agent");
		}
	}

	if (userLoading) {
		return (
			<div className="flex h-full items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (!user?.is_superuser) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-4 p-6">
				<h1 className="text-2xl font-semibold">Access denied</h1>
				<p className="text-muted-foreground">You must be a superuser to view this page.</p>
			</div>
		);
	}

	return (
		<div className="container mx-auto max-w-5xl p-6">
			<div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="text-2xl font-semibold">Agent registry</h1>
					<p className="text-sm text-muted-foreground">Manage vertical-client agent configs.</p>
				</div>
				<div className="flex items-center gap-2">
					<Input
						placeholder="Filter by client_id"
						value={filterClientId}
						onChange={(e) => setFilterClientId(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter") {
								void loadAgents(filterClientId.trim() || undefined);
							}
						}}
						className="w-56"
					/>
					<Button onClick={() => void loadAgents(filterClientId.trim() || undefined)}>
						Refresh
					</Button>
					<Button onClick={openCreate}>Add agent</Button>
				</div>
			</div>

			{loading ? (
				<div className="flex h-64 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : filteredAgents.length === 0 ? (
				<Card>
					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
						No agent configs found.
					</CardContent>
				</Card>
			) : (
				<div className="grid gap-4 sm:grid-cols-2">
					{filteredAgents.map((agent) => (
						<Card key={agent.id}>
							<CardHeader>
								<div className="flex items-start justify-between">
									<div>
										<CardTitle>{agent.display_name}</CardTitle>
										<CardDescription>
											{agent.client_id} / {agent.slug}
										</CardDescription>
									</div>
									<div className="flex gap-1">
										{agent.is_active ? (
											<Badge variant="default">Active</Badge>
										) : (
											<Badge variant="secondary">Inactive</Badge>
										)}
										{agent.citations_enabled && <Badge variant="outline">Citations</Badge>}
									</div>
								</div>
							</CardHeader>
							<CardContent className="space-y-2">
								<div className="text-sm text-muted-foreground">
									<span className="font-medium">Name:</span> {agent.name}
								</div>
								{agent.model_name && (
									<div className="text-sm text-muted-foreground">
										<span className="font-medium">Model:</span> {agent.model_name}
									</div>
								)}
								{agent.enabled_tools.length > 0 && (
									<div className="text-sm text-muted-foreground">
										<span className="font-medium">Tools:</span> {agent.enabled_tools.join(", ")}
									</div>
								)}
								<div className="flex justify-end gap-2 pt-2">
									<Button variant="outline" size="sm" onClick={() => openEdit(agent)}>
										Edit
									</Button>
									<Button variant="destructive" size="sm" onClick={() => void handleDelete(agent)}>
										Deactivate
									</Button>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
				<DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
					<DialogHeader>
						<DialogTitle>{editAgent ? "Edit agent" : "Add agent"}</DialogTitle>
						<DialogDescription>
							{editAgent
								? "Update the agent configuration below."
								: "Create a new agent config. Client ID must match a registered vertical client."}
						</DialogDescription>
					</DialogHeader>

					<div className="grid gap-4 py-4 sm:grid-cols-2">
						<div className="space-y-2">
							<Label htmlFor="client_id">Client ID</Label>
							<Input
								id="client_id"
								value={draft.client_id}
								disabled={!!editAgent}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										client_id: e.target.value,
									}))
								}
								placeholder="bdsai.vn"
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="slug">Slug</Label>
							<Input
								id="slug"
								value={draft.slug}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										slug: e.target.value,
									}))
								}
								placeholder="bdsai-listing-assistant"
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="name">Name</Label>
							<Input
								id="name"
								value={draft.name}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										name: e.target.value,
									}))
								}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="display_name">Display name</Label>
							<Input
								id="display_name"
								value={draft.display_name}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										display_name: e.target.value,
									}))
								}
							/>
						</div>

						<div className="space-y-2 sm:col-span-2">
							<Label htmlFor="system_instructions">System instructions</Label>
							<Textarea
								id="system_instructions"
								value={draft.system_instructions ?? ""}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										system_instructions: e.target.value,
									}))
								}
								rows={4}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="enabled_tools">Enabled tools (comma-separated)</Label>
							<Input
								id="enabled_tools"
								value={toolArrayToString(draft.enabled_tools)}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										enabled_tools: toolStringToArray(e.target.value),
									}))
								}
								placeholder="update_memory, create_automation"
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="disabled_tools">Disabled tools (comma-separated)</Label>
							<Input
								id="disabled_tools"
								value={toolArrayToString(draft.disabled_tools)}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										disabled_tools: toolStringToArray(e.target.value),
									}))
								}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="model_name">Model name</Label>
							<Input
								id="model_name"
								value={draft.model_name ?? ""}
								onChange={(e) =>
									setDraft((prev) => ({
										...prev,
										model_name: e.target.value,
									}))
								}
								placeholder="gpt-4o"
							/>
						</div>

						<div className="flex items-center gap-4 pt-2">
							<div className="flex items-center gap-2">
								<Switch
									id="citations_enabled"
									checked={draft.citations_enabled}
									onCheckedChange={(checked) =>
										setDraft((prev) => ({ ...prev, citations_enabled: checked }))
									}
								/>
								<Label htmlFor="citations_enabled" className="cursor-pointer">
									Citations
								</Label>
							</div>

							<div className="flex items-center gap-2">
								<Switch
									id="is_active"
									checked={draft.is_active}
									onCheckedChange={(checked) =>
										setDraft((prev) => ({ ...prev, is_active: checked }))
									}
								/>
								<Label htmlFor="is_active" className="cursor-pointer">
									Active
								</Label>
							</div>
						</div>
					</div>

					<DialogFooter>
						<Button variant="outline" onClick={closeDialog} disabled={isSubmitting}>
							Cancel
						</Button>
						<Button onClick={() => void handleSave()} disabled={isSubmitting}>
							{isSubmitting ? "Saving..." : editAgent ? "Save changes" : "Create"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
