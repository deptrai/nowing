"use client";

import { useAtom, useAtomValue } from "jotai";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
	adminGlobalModelConnectionsAtom,
	bulkUpdateAdminGlobalModelsMutationAtom,
	createAdminGlobalConnectionMutationAtom,
	deleteAdminGlobalConnectionMutationAtom,
	discoverAdminGlobalConnectionModelsMutationAtom,
	previewAdminGlobalConnectionModelsMutationAtom,
	testAdminGlobalConnectionModelMutationAtom,
	testAdminGlobalConnectionPreviewMutationAtom,
	updateAdminGlobalConnectionMutationAtom,
	updateAdminGlobalModelMutationAtom,
} from "@/atoms/model-connections/admin-global-model-connections.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import {
	PROVIDER_ORDER,
	providerDefaultBaseUrl,
	providerDisplay,
	providerIcon,
} from "@/components/settings/model-connections/provider-metadata";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type {
	AdminGlobalConnectionCreateRequest,
	AdminGlobalConnectionRead,
	AdminGlobalConnectionUpdateRequest,
	AdminGlobalModelPreviewRead,
	AdminGlobalModelRead,
	AdminGlobalModelUpdateRequest,
} from "@/contracts/types/admin-global-model-connections.types";
import { cn } from "@/lib/utils";

interface ConnectionDraft {
	provider: string;
	base_url: string;
	api_key: string;
	enabled: boolean;
	extra: Record<string, unknown>;
}

interface ModelDraft {
	model_id: string;
	display_name: string;
	supports_chat: boolean;
	max_input_tokens: string;
	supports_image_input: boolean;
	supports_tools: boolean;
	supports_image_generation: boolean;
	enabled: boolean;
	cost_per_1k_input_tokens: string;
	cost_per_1k_output_tokens: string;
	rpm: string;
	tpm: string;
}

const emptyConnection: ConnectionDraft = {
	provider: "",
	base_url: "",
	api_key: "",
	enabled: true,
	extra: {},
};

const emptyModel: ModelDraft = {
	model_id: "",
	display_name: "",
	supports_chat: true,
	max_input_tokens: "",
	supports_image_input: false,
	supports_tools: false,
	supports_image_generation: false,
	enabled: true,
	cost_per_1k_input_tokens: "",
	cost_per_1k_output_tokens: "",
	rpm: "",
	tpm: "",
};

function toNumber(value: string): number | null {
	const trimmed = value.trim();
	if (trimmed === "") return null;
	const parsed = Number(trimmed);
	return Number.isFinite(parsed) ? parsed : null;
}

function buildCreateRequest(
	connection: ConnectionDraft,
	model: ModelDraft
): AdminGlobalConnectionCreateRequest {
	return {
		provider: connection.provider.trim(),
		base_url: connection.base_url.trim() || null,
		api_key: connection.api_key.trim() || null,
		extra: connection.extra,
		enabled: connection.enabled,
		models: [
			{
				model_id: model.model_id.trim(),
				display_name: model.display_name.trim() || null,
				supports_chat: model.supports_chat,
				max_input_tokens: toNumber(model.max_input_tokens),
				supports_image_input: model.supports_image_input,
				supports_tools: model.supports_tools,
				supports_image_generation: model.supports_image_generation,
				enabled: model.enabled,
				metadata: {},
				billing_tier: "free",
				pricing: {
					cost_per_1k_input_tokens: toNumber(model.cost_per_1k_input_tokens),
					cost_per_1k_output_tokens: toNumber(model.cost_per_1k_output_tokens),
					rpm: toNumber(model.rpm),
					tpm: toNumber(model.tpm),
					router_pool_eligible: true,
				},
			},
		],
	};
}

function buildUpdateRequest(connection: ConnectionDraft): AdminGlobalConnectionUpdateRequest {
	return {
		provider: connection.provider.trim() || null,
		base_url: connection.base_url.trim() || null,
		api_key: connection.api_key.trim() || null,
		extra: connection.extra,
		enabled: connection.enabled,
	};
}

function buildModelUpdateRequest(model: ModelDraft): AdminGlobalModelUpdateRequest {
	return {
		display_name: model.display_name.trim() || null,
		enabled: model.enabled,
		supports_chat: model.supports_chat,
		max_input_tokens: toNumber(model.max_input_tokens),
		supports_image_input: model.supports_image_input,
		supports_tools: model.supports_tools,
		supports_image_generation: model.supports_image_generation,
		pricing: {
			cost_per_1k_input_tokens: toNumber(model.cost_per_1k_input_tokens),
			cost_per_1k_output_tokens: toNumber(model.cost_per_1k_output_tokens),
			rpm: toNumber(model.rpm),
			tpm: toNumber(model.tpm),
			router_pool_eligible: true,
		},
	};
}

function modelDraftFromPreview(
	model: AdminGlobalModelPreviewRead | AdminGlobalModelRead
): ModelDraft {
	return {
		model_id: model.model_id,
		display_name: model.display_name ?? "",
		supports_chat: model.supports_chat ?? true,
		max_input_tokens: String(model.max_input_tokens ?? ""),
		supports_image_input: model.supports_image_input ?? false,
		supports_tools: model.supports_tools ?? false,
		supports_image_generation: model.supports_image_generation ?? false,
		enabled: model.enabled,
		cost_per_1k_input_tokens: String(model.cost_per_1k_input_tokens ?? ""),
		cost_per_1k_output_tokens: String(model.cost_per_1k_output_tokens ?? ""),
		rpm: String(model.rpm ?? ""),
		tpm: String(model.tpm ?? ""),
	};
}

export default function GlobalModelConnectionsAdminPage() {
	const [{ data: user, isLoading: userLoading }] = useAtom(currentUserAtom);
	const [{ data: connections = [], isLoading: listLoading }] = useAtom(
		adminGlobalModelConnectionsAtom
	);

	const create = useAtomValue(createAdminGlobalConnectionMutationAtom);
	const update = useAtomValue(updateAdminGlobalConnectionMutationAtom);
	const deleteConnection = useAtomValue(deleteAdminGlobalConnectionMutationAtom);
	const preview = useAtomValue(previewAdminGlobalConnectionModelsMutationAtom);
	const testPreview = useAtomValue(testAdminGlobalConnectionPreviewMutationAtom);
	const discover = useAtomValue(discoverAdminGlobalConnectionModelsMutationAtom);
	const testSaved = useAtomValue(testAdminGlobalConnectionModelMutationAtom);
	const updateModel = useAtomValue(updateAdminGlobalModelMutationAtom);
	const bulkUpdateModels = useAtomValue(bulkUpdateAdminGlobalModelsMutationAtom);

	const [createOpen, setCreateOpen] = useState(false);
	const [draft, setDraft] = useState<ConnectionDraft>(emptyConnection);
	const [model, setModel] = useState<ModelDraft>(emptyModel);
	const [previewModels, setPreviewModels] = useState<AdminGlobalModelPreviewRead[]>([]);

	const [editDialog, setEditDialog] = useState<{
		open: boolean;
		connection: AdminGlobalConnectionRead | null;
	}>({
		open: false,
		connection: null,
	});
	const [editDraft, setEditDraft] = useState<ConnectionDraft>(emptyConnection);

	const [testDialog, setTestDialog] = useState<{
		open: boolean;
		connection: AdminGlobalConnectionRead | null;
		modelId: string;
	}>({ open: false, connection: null, modelId: "" });

	const [discoverDialog, setDiscoverDialog] = useState<{
		open: boolean;
		connection: AdminGlobalConnectionRead | null;
		models: AdminGlobalModelPreviewRead[];
	}>({ open: false, connection: null, models: [] });

	const [modelEditDialog, setModelEditDialog] = useState<{
		open: boolean;
		connection: AdminGlobalConnectionRead | null;
		model: AdminGlobalModelRead | null;
		draft: ModelDraft;
	}>({ open: false, connection: null, model: null, draft: emptyModel });

	const [deleteDialog, setDeleteDialog] = useState<{
		open: boolean;
		connection: AdminGlobalConnectionRead | null;
	}>({
		open: false,
		connection: null,
	});

	useEffect(() => {
		if (!createOpen) {
			setDraft(emptyConnection);
			setModel(emptyModel);
			setPreviewModels([]);
		}
	}, [createOpen]);

	useEffect(() => {
		if (editDialog.open && editDialog.connection) {
			setEditDraft({
				provider: editDialog.connection.provider,
				base_url: editDialog.connection.base_url ?? "",
				api_key: "",
				enabled: editDialog.connection.enabled,
				extra: editDialog.connection.extra,
			});
		}
	}, [editDialog.open, editDialog.connection]);

	const isCreateValid = useMemo(
		() => draft.provider.trim().length > 0 && model.model_id.trim().length > 0,
		[draft.provider, model.model_id]
	);

	const sortedProviders = useMemo(
		() =>
			[...PROVIDER_ORDER, "custom"].filter((value, index, self) => self.indexOf(value) === index),
		[]
	);

	function handleProviderChange(value: string) {
		setDraft((prev) => ({
			...prev,
			provider: value,
			base_url: prev.base_url || providerDefaultBaseUrl(value) || "",
		}));
	}

	async function handleDiscoverPreview() {
		if (!isCreateValid) {
			toast.error("Provider and model ID are required to discover models");
			return;
		}
		try {
			const request = buildCreateRequest(draft, model);
			const models = await preview.mutateAsync(request);
			setPreviewModels(models);
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleTestPreview() {
		if (!isCreateValid) {
			toast.error("Provider and model ID are required to test");
			return;
		}
		try {
			const request = buildCreateRequest(draft, model);
			await testPreview.mutateAsync({ ...request, model_id: model.model_id.trim() });
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleCreate() {
		if (!isCreateValid) {
			toast.error("Provider and model ID are required");
			return;
		}
		try {
			const request = buildCreateRequest(draft, model);
			await create.mutateAsync(request);
			setCreateOpen(false);
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleUpdate() {
		if (!editDialog.connection) return;
		try {
			await update.mutateAsync({
				id: editDialog.connection.id,
				data: buildUpdateRequest(editDraft),
			});
			setEditDialog({ open: false, connection: null });
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleDelete() {
		if (!deleteDialog.connection) return;
		try {
			await deleteConnection.mutateAsync(deleteDialog.connection.id);
			setDeleteDialog({ open: false, connection: null });
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleToggleConnectionEnabled(connection: AdminGlobalConnectionRead) {
		try {
			await update.mutateAsync({
				id: connection.id,
				data: { enabled: !connection.enabled },
			});
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleDiscoverSaved(connection: AdminGlobalConnectionRead) {
		try {
			const models = await discover.mutateAsync(connection.id);
			setDiscoverDialog({ open: true, connection, models });
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleTestSaved() {
		if (!testDialog.connection || !testDialog.modelId) return;
		try {
			await testSaved.mutateAsync({
				id: testDialog.connection.id,
				data: { model_id: testDialog.modelId },
			});
			setTestDialog({ open: false, connection: null, modelId: "" });
		} catch {
			// Error is handled by the mutation
		}
	}

	function openTestDialog(connection: AdminGlobalConnectionRead) {
		setTestDialog({
			open: true,
			connection,
			modelId:
				connection.models.find((m) => m.enabled)?.model_id ?? connection.models[0]?.model_id ?? "",
		});
	}

	function openEditModelDialog(
		connection: AdminGlobalConnectionRead,
		modelItem: AdminGlobalModelRead
	) {
		setModelEditDialog({
			open: true,
			connection,
			model: modelItem,
			draft: modelDraftFromPreview(modelItem),
		});
	}

	async function handleUpdateModel() {
		if (!modelEditDialog.model) return;
		try {
			await updateModel.mutateAsync({
				id: modelEditDialog.model.id,
				data: buildModelUpdateRequest(modelEditDialog.draft),
			});
			setModelEditDialog({ open: false, connection: null, model: null, draft: emptyModel });
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleToggleModelEnabled(
		_connection: AdminGlobalConnectionRead,
		modelItem: AdminGlobalModelRead
	) {
		try {
			await updateModel.mutateAsync({
				id: modelItem.id,
				data: { enabled: !modelItem.enabled },
			});
		} catch {
			// Error is handled by the mutation
		}
	}

	async function handleBulkEnable(connection: AdminGlobalConnectionRead, enabled: boolean) {
		try {
			await bulkUpdateModels.mutateAsync({
				connectionId: connection.id,
				data: { model_ids: connection.models.map((m) => m.id), enabled },
			});
		} catch {
			// Error is handled by the mutation
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
			<div className="mb-6 flex items-center justify-between">
				<div>
					<h1 className="font-serif text-2xl sm:text-3xl font-normal">Global model connections</h1>
					<p className="text-xs sm:text-sm text-muted-foreground font-sans">
						Manage platform-level LLM connections and models.
					</p>
				</div>
				<Button onClick={() => setCreateOpen(true)}>Add managed connection</Button>
			</div>

			{listLoading ? (
				<div className="flex h-64 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : connections.length === 0 ? (
				<Card>
					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
						No global model connections found.
					</CardContent>
				</Card>
			) : (
				<div className="space-y-4">
					{connections.map((connection) => {
						const meta = providerDisplay(connection.provider);
						const isManaged = connection.source === "managed";
						return (
							<Card
								key={connection.id}
								className={cn(
									"overflow-hidden",
									!connection.enabled && "border-muted-foreground/20 bg-muted/30"
								)}
							>
								<CardHeader className="pb-3">
									<div className="flex items-start justify-between gap-4">
										<div className="flex items-center gap-3">
											{providerIcon(connection.provider, "size-5")}
											<div>
												<CardTitle>{meta.name}</CardTitle>
												<CardDescription>
													{connection.provider}
													{connection.base_url ? ` · ${connection.base_url}` : ""}
												</CardDescription>
											</div>
										</div>
										<div className="flex items-center gap-2">
											<span
												className={cn(
													"inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
													connection.source === "managed"
														? "bg-primary/10 text-primary"
														: connection.source === "file"
															? "bg-muted text-muted-foreground"
															: "bg-accent text-accent-foreground"
												)}
											>
												{connection.source}
											</span>
											{isManaged ? (
												<Switch
													checked={connection.enabled}
													onCheckedChange={() => handleToggleConnectionEnabled(connection)}
													aria-label="Toggle connection"
												/>
											) : (
												<span className="text-sm text-muted-foreground">
													{connection.enabled ? "Enabled" : "Disabled"}
												</span>
											)}
										</div>
									</div>
								</CardHeader>
								<CardContent className="space-y-4">
									{isManaged && (
										<div className="flex flex-wrap items-center gap-2">
											<Button
												variant="outline"
												size="sm"
												onClick={() => setEditDialog({ open: true, connection })}
											>
												Edit
											</Button>
											<Button
												variant="outline"
												size="sm"
												onClick={() => openTestDialog(connection)}
												disabled={connection.models.length === 0}
											>
												Test
											</Button>
											<Button
												variant="outline"
												size="sm"
												onClick={() => handleDiscoverSaved(connection)}
											>
												Discover
											</Button>
											<Button
												variant="outline"
												size="sm"
												onClick={() => setDeleteDialog({ open: true, connection })}
											>
												Delete
											</Button>
											<Button
												variant="secondary"
												size="sm"
												onClick={() =>
													handleBulkEnable(connection, !connection.models.every((m) => m.enabled))
												}
											>
												{connection.models.every((m) => m.enabled)
													? "Disable all models"
													: "Enable all models"}
											</Button>
										</div>
									)}

									<Separator />

									<div className="space-y-2">
										<h4 className="text-sm font-medium">Models</h4>
										{connection.models.length === 0 ? (
											<p className="text-sm text-muted-foreground">No models</p>
										) : (
											<div className="divide-y rounded-md border">
												{connection.models.map((modelItem) => (
													<div
														key={modelItem.id}
														className="flex items-start justify-between gap-4 p-3"
													>
														<div className="min-w-0 flex-1">
															<p className="truncate text-sm font-medium">
																{modelItem.display_name || modelItem.model_id}
															</p>
															<p className="truncate text-xs text-muted-foreground">
																{modelItem.model_id}
															</p>
															<div className="mt-1 flex flex-wrap gap-1 text-xs text-muted-foreground">
																{modelItem.supports_chat && <span>chat</span>}
																{modelItem.supports_image_input && <span>vision</span>}
																{modelItem.supports_tools && <span>tools</span>}
																{modelItem.supports_image_generation && <span>image</span>}
															</div>
														</div>
														<div className="flex items-center gap-2">
															<span className="text-xs text-muted-foreground">
																{modelItem.enabled ? "Enabled" : "Disabled"}
															</span>
															{isManaged && modelItem.can_edit && (
																<>
																	<Switch
																		checked={modelItem.enabled}
																		onCheckedChange={() =>
																			handleToggleModelEnabled(connection, modelItem)
																		}
																		aria-label="Toggle model"
																	/>
																	<Button
																		variant="ghost"
																		size="sm"
																		onClick={() => openEditModelDialog(connection, modelItem)}
																	>
																		Edit
																	</Button>
																</>
															)}
														</div>
													</div>
												))}
											</div>
										)}
									</div>
								</CardContent>
							</Card>
						);
					})}
				</div>
			)}

			{/* Create dialog */}
			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
				<DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
					<DialogHeader>
						<DialogTitle>Add global connection</DialogTitle>
						<DialogDescription>
							Configure a provider, test it, and save it as a managed global connection.
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-6 py-4">
						<div className="space-y-3">
							<h3 className="text-sm font-medium">Provider</h3>
							<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
								<div className="space-y-2">
									<Label htmlFor="provider">Provider</Label>
									<Select value={draft.provider} onValueChange={handleProviderChange}>
										<SelectTrigger id="provider">
											<SelectValue placeholder="Select a provider" />
										</SelectTrigger>
										<SelectContent>
											{sortedProviders.map((p) => (
												<SelectItem key={p} value={p}>
													{p}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</div>
								<div className="space-y-2">
									<Label htmlFor="base_url">Base URL</Label>
									<Input
										id="base_url"
										value={draft.base_url}
										onChange={(event) =>
											setDraft((prev) => ({ ...prev, base_url: event.target.value }))
										}
										placeholder="https://api.openai.com/v1"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="api_key">API key</Label>
									<Input
										id="api_key"
										type="password"
										value={draft.api_key}
										onChange={(event) =>
											setDraft((prev) => ({ ...prev, api_key: event.target.value }))
										}
									/>
								</div>
								<div className="flex items-center gap-2">
									<Switch
										id="enabled"
										checked={draft.enabled}
										onCheckedChange={(checked) =>
											setDraft((prev) => ({ ...prev, enabled: checked }))
										}
									/>
									<Label htmlFor="enabled">Enabled on save</Label>
								</div>
							</div>
						</div>

						<Separator />

						<div className="space-y-3">
							<h3 className="text-sm font-medium">Model</h3>
							<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
								<div className="space-y-2">
									<Label htmlFor="model_id">Model ID</Label>
									<Input
										id="model_id"
										value={model.model_id}
										onChange={(event) =>
											setModel((prev) => ({ ...prev, model_id: event.target.value }))
										}
										placeholder="gpt-4o"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="display_name">Display name</Label>
									<Input
										id="display_name"
										value={model.display_name}
										onChange={(event) =>
											setModel((prev) => ({ ...prev, display_name: event.target.value }))
										}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="max_input_tokens">Max input tokens</Label>
									<Input
										id="max_input_tokens"
										type="number"
										value={model.max_input_tokens}
										onChange={(event) =>
											setModel((prev) => ({ ...prev, max_input_tokens: event.target.value }))
										}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="cost_per_1k_input_tokens">Cost per 1k input tokens</Label>
									<Input
										id="cost_per_1k_input_tokens"
										type="number"
										step="0.0001"
										value={model.cost_per_1k_input_tokens}
										onChange={(event) =>
											setModel((prev) => ({
												...prev,
												cost_per_1k_input_tokens: event.target.value,
											}))
										}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="cost_per_1k_output_tokens">Cost per 1k output tokens</Label>
									<Input
										id="cost_per_1k_output_tokens"
										type="number"
										step="0.0001"
										value={model.cost_per_1k_output_tokens}
										onChange={(event) =>
											setModel((prev) => ({
												...prev,
												cost_per_1k_output_tokens: event.target.value,
											}))
										}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="rpm">RPM</Label>
									<Input
										id="rpm"
										type="number"
										value={model.rpm}
										onChange={(event) => setModel((prev) => ({ ...prev, rpm: event.target.value }))}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="tpm">TPM</Label>
									<Input
										id="tpm"
										type="number"
										value={model.tpm}
										onChange={(event) => setModel((prev) => ({ ...prev, tpm: event.target.value }))}
									/>
								</div>
							</div>

							<div className="grid grid-cols-2 gap-4 md:grid-cols-4">
								<div className="flex items-center gap-2">
									<Switch
										id="supports_chat"
										checked={model.supports_chat}
										onCheckedChange={(checked) =>
											setModel((prev) => ({ ...prev, supports_chat: checked }))
										}
									/>
									<Label htmlFor="supports_chat">Chat</Label>
								</div>
								<div className="flex items-center gap-2">
									<Switch
										id="supports_image_input"
										checked={model.supports_image_input}
										onCheckedChange={(checked) =>
											setModel((prev) => ({ ...prev, supports_image_input: checked }))
										}
									/>
									<Label htmlFor="supports_image_input">Vision</Label>
								</div>
								<div className="flex items-center gap-2">
									<Switch
										id="supports_tools"
										checked={model.supports_tools}
										onCheckedChange={(checked) =>
											setModel((prev) => ({ ...prev, supports_tools: checked }))
										}
									/>
									<Label htmlFor="supports_tools">Tools</Label>
								</div>
								<div className="flex items-center gap-2">
									<Switch
										id="supports_image_generation"
										checked={model.supports_image_generation}
										onCheckedChange={(checked) =>
											setModel((prev) => ({ ...prev, supports_image_generation: checked }))
										}
									/>
									<Label htmlFor="supports_image_generation">Image</Label>
								</div>
							</div>
						</div>

						{previewModels.length > 0 && (
							<div className="space-y-2">
								<h3 className="text-sm font-medium">Discovered models</h3>
								<div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
									{previewModels.map((previewModel) => (
										<Button
											key={previewModel.model_id}
											variant="outline"
											size="sm"
											className="justify-start"
											onClick={() => setModel(modelDraftFromPreview(previewModel))}
										>
											{previewModel.display_name || previewModel.model_id}
										</Button>
									))}
								</div>
							</div>
						)}

						<div className="flex flex-wrap gap-2">
							<Button
								variant="outline"
								onClick={handleDiscoverPreview}
								disabled={preview.isPending}
							>
								{preview.isPending ? <Spinner size="xs" /> : "Discover models"}
							</Button>
							<Button
								variant="outline"
								onClick={handleTestPreview}
								disabled={testPreview.isPending}
							>
								{testPreview.isPending ? <Spinner size="xs" /> : "Test model"}
							</Button>
							<Button onClick={handleCreate} disabled={!isCreateValid || create.isPending}>
								{create.isPending ? <Spinner size="xs" /> : "Save connection"}
							</Button>
						</div>
					</div>
				</DialogContent>
			</Dialog>

			{/* Edit connection dialog */}
			<Dialog
				open={editDialog.open}
				onOpenChange={(open) => setEditDialog({ open, connection: editDialog.connection })}
			>
				<DialogContent className="max-w-lg">
					<DialogHeader>
						<DialogTitle>Edit connection</DialogTitle>
					</DialogHeader>
					<div className="space-y-4 py-4">
						<div className="space-y-2">
							<Label htmlFor="edit_provider">Provider</Label>
							<Input
								id="edit_provider"
								value={editDraft.provider}
								onChange={(event) =>
									setEditDraft((prev) => ({ ...prev, provider: event.target.value }))
								}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="edit_base_url">Base URL</Label>
							<Input
								id="edit_base_url"
								value={editDraft.base_url}
								onChange={(event) =>
									setEditDraft((prev) => ({ ...prev, base_url: event.target.value }))
								}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="edit_api_key">API key (leave blank to keep unchanged)</Label>
							<Input
								id="edit_api_key"
								type="password"
								value={editDraft.api_key}
								onChange={(event) =>
									setEditDraft((prev) => ({ ...prev, api_key: event.target.value }))
								}
							/>
						</div>
						<div className="flex items-center gap-2">
							<Switch
								id="edit_enabled"
								checked={editDraft.enabled}
								onCheckedChange={(checked) =>
									setEditDraft((prev) => ({ ...prev, enabled: checked }))
								}
							/>
							<Label htmlFor="edit_enabled">Enabled</Label>
						</div>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setEditDialog({ open: false, connection: null })}
						>
							Cancel
						</Button>
						<Button onClick={handleUpdate} disabled={update.isPending}>
							{update.isPending ? <Spinner size="xs" /> : "Save"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Test saved connection dialog */}
			<Dialog
				open={testDialog.open}
				onOpenChange={(open) =>
					setTestDialog({ open, connection: testDialog.connection, modelId: testDialog.modelId })
				}
			>
				<DialogContent className="max-w-lg">
					<DialogHeader>
						<DialogTitle>Test model</DialogTitle>
						<DialogDescription>
							Select a model from {testDialog.connection?.provider} to test.
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-4 py-4">
						<div className="space-y-2">
							<Label htmlFor="test_model">Model</Label>
							<Select
								value={testDialog.modelId}
								onValueChange={(value) => setTestDialog((prev) => ({ ...prev, modelId: value }))}
							>
								<SelectTrigger id="test_model">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{testDialog.connection?.models.map((modelItem) => (
										<SelectItem key={modelItem.id} value={modelItem.model_id}>
											{modelItem.display_name || modelItem.model_id}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
						</div>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setTestDialog({ open: false, connection: null, modelId: "" })}
						>
							Cancel
						</Button>
						<Button onClick={handleTestSaved} disabled={testSaved.isPending}>
							{testSaved.isPending ? <Spinner size="xs" /> : "Test"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Discover results dialog */}
			<Dialog
				open={discoverDialog.open}
				onOpenChange={(open) =>
					setDiscoverDialog({
						open,
						connection: discoverDialog.connection,
						models: discoverDialog.models,
					})
				}
			>
				<DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
					<DialogHeader>
						<DialogTitle>Discovered models</DialogTitle>
						<DialogDescription>
							Models found for {discoverDialog.connection?.provider}. These are not saved yet.
						</DialogDescription>
					</DialogHeader>
					<div className="space-y-3 py-4">
						{discoverDialog.models.length === 0 ? (
							<p className="text-muted-foreground">No models discovered.</p>
						) : (
							discoverDialog.models.map((modelItem) => (
								<div key={modelItem.model_id} className="rounded-md border p-3">
									<p className="font-medium">{modelItem.display_name || modelItem.model_id}</p>
									<p className="text-sm text-muted-foreground">{modelItem.model_id}</p>
								</div>
							))
						)}
					</div>
					<DialogFooter>
						<Button
							onClick={() => setDiscoverDialog({ open: false, connection: null, models: [] })}
						>
							Close
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Edit model dialog */}
			<Dialog
				open={modelEditDialog.open}
				onOpenChange={(open) => setModelEditDialog({ ...modelEditDialog, open })}
			>
				<DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
					<DialogHeader>
						<DialogTitle>Edit model</DialogTitle>
					</DialogHeader>
					<div className="space-y-4 py-4">
						<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
							<div className="space-y-2">
								<Label htmlFor="edit_model_id">Model ID</Label>
								<Input id="edit_model_id" value={modelEditDialog.draft.model_id} disabled />
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_display_name">Display name</Label>
								<Input
									id="edit_model_display_name"
									value={modelEditDialog.draft.display_name}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, display_name: event.target.value },
										}))
									}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_max_input_tokens">Max input tokens</Label>
								<Input
									id="edit_model_max_input_tokens"
									type="number"
									value={modelEditDialog.draft.max_input_tokens}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, max_input_tokens: event.target.value },
										}))
									}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_cost_input">Cost per 1k input</Label>
								<Input
									id="edit_model_cost_input"
									type="number"
									step="0.0001"
									value={modelEditDialog.draft.cost_per_1k_input_tokens}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, cost_per_1k_input_tokens: event.target.value },
										}))
									}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_cost_output">Cost per 1k output</Label>
								<Input
									id="edit_model_cost_output"
									type="number"
									step="0.0001"
									value={modelEditDialog.draft.cost_per_1k_output_tokens}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, cost_per_1k_output_tokens: event.target.value },
										}))
									}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_rpm">RPM</Label>
								<Input
									id="edit_model_rpm"
									type="number"
									value={modelEditDialog.draft.rpm}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, rpm: event.target.value },
										}))
									}
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="edit_model_tpm">TPM</Label>
								<Input
									id="edit_model_tpm"
									type="number"
									value={modelEditDialog.draft.tpm}
									onChange={(event) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, tpm: event.target.value },
										}))
									}
								/>
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4 md:grid-cols-4">
							<div className="flex items-center gap-2">
								<Switch
									id="edit_model_supports_chat"
									checked={modelEditDialog.draft.supports_chat}
									onCheckedChange={(checked) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, supports_chat: checked },
										}))
									}
								/>
								<Label htmlFor="edit_model_supports_chat">Chat</Label>
							</div>
							<div className="flex items-center gap-2">
								<Switch
									id="edit_model_supports_image_input"
									checked={modelEditDialog.draft.supports_image_input}
									onCheckedChange={(checked) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, supports_image_input: checked },
										}))
									}
								/>
								<Label htmlFor="edit_model_supports_image_input">Vision</Label>
							</div>
							<div className="flex items-center gap-2">
								<Switch
									id="edit_model_supports_tools"
									checked={modelEditDialog.draft.supports_tools}
									onCheckedChange={(checked) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, supports_tools: checked },
										}))
									}
								/>
								<Label htmlFor="edit_model_supports_tools">Tools</Label>
							</div>
							<div className="flex items-center gap-2">
								<Switch
									id="edit_model_supports_image_generation"
									checked={modelEditDialog.draft.supports_image_generation}
									onCheckedChange={(checked) =>
										setModelEditDialog((prev) => ({
											...prev,
											draft: { ...prev.draft, supports_image_generation: checked },
										}))
									}
								/>
								<Label htmlFor="edit_model_supports_image_generation">Image</Label>
							</div>
						</div>

						<div className="flex items-center gap-2">
							<Switch
								id="edit_model_enabled"
								checked={modelEditDialog.draft.enabled}
								onCheckedChange={(checked) =>
									setModelEditDialog((prev) => ({
										...prev,
										draft: { ...prev.draft, enabled: checked },
									}))
								}
							/>
							<Label htmlFor="edit_model_enabled">Enabled</Label>
						</div>
					</div>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() =>
								setModelEditDialog({
									open: false,
									connection: null,
									model: null,
									draft: emptyModel,
								})
							}
						>
							Cancel
						</Button>
						<Button onClick={handleUpdateModel} disabled={updateModel.isPending}>
							{updateModel.isPending ? <Spinner size="xs" /> : "Save"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Delete confirmation dialog */}
			<Dialog
				open={deleteDialog.open}
				onOpenChange={(open) => setDeleteDialog({ open, connection: deleteDialog.connection })}
			>
				<DialogContent className="max-w-md">
					<DialogHeader>
						<DialogTitle>Delete connection?</DialogTitle>
						<DialogDescription>
							This will remove the managed connection for {deleteDialog.connection?.provider}.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setDeleteDialog({ open: false, connection: null })}
						>
							Cancel
						</Button>
						<Button
							variant="destructive"
							onClick={handleDelete}
							disabled={deleteConnection.isPending}
						>
							{deleteConnection.isPending ? <Spinner size="xs" /> : "Delete"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
