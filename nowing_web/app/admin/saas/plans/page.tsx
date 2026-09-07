"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Edit, Layers, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { PlanDefinition } from "@/contracts/types/workspace.types";
import {
	adminSaasApiService,
	type CreatePlanPayload,
	type UpdatePlanPayload,
} from "@/lib/apis/admin-saas-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

function formatBytes(value: number | null | undefined): string {
	if (!value || value <= 0) return "Unlimited";
	const units = ["B", "KB", "MB", "GB", "TB"];
	const i = Math.floor(Math.log10(value) / 3);
	const unit = units[Math.min(i, units.length - 1)];
	const scaled = value / 10 ** (i * 3);
	return `${scaled.toFixed(0)} ${unit}`;
}

function formatCurrency(priceMicros: number | null | undefined, currency = "USD"): string {
	if (priceMicros === null || priceMicros === undefined || priceMicros <= 0) return "Free";
	const amount = priceMicros / 1_000_000;
	return new Intl.NumberFormat(undefined, {
		style: "currency",
		currency,
		maximumFractionDigits: 0,
	}).format(amount);
}

export default function AdminSaasPlansPage() {
	const queryClient = useQueryClient();

	const [isCreateOpen, setIsCreateOpen] = useState(false);
	const [editingPlan, setEditingPlan] = useState<PlanDefinition | null>(null);
	const [deletingPlanTier, setDeletingPlanTier] = useState<string | null>(null);

	// Form states
	const [formTier, setFormTier] = useState("");
	const [formDocs, setFormDocs] = useState<string>("");
	const [formMembers, setFormMembers] = useState<string>("");
	const [formRuns, setFormRuns] = useState<string>("");
	const [formStorageGb, setFormStorageGb] = useState<string>("");
	const [formCredits, setFormCredits] = useState<string>("");
	const [formSources, setFormSources] = useState<string>("");
	const [formSupport, setFormSupport] = useState<string>("email");
	const [formPriceDollars, setFormPriceDollars] = useState<string>("0");
	const [formCurrency, setFormCurrency] = useState<string>("USD");

	const { data: plans, isLoading } = useQuery({
		queryKey: cacheKeys.admin.saasPlans(),
		queryFn: () => adminSaasApiService.listPlans(),
	});

	const createMutation = useMutation({
		mutationFn: (payload: CreatePlanPayload) => adminSaasApiService.createPlan(payload),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.admin.saasPlans() });
			setIsCreateOpen(false);
			resetForm();
			toast.success("Plan tier created successfully");
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to create plan");
		},
	});

	const updateMutation = useMutation({
		mutationFn: (vars: { tier: string; payload: UpdatePlanPayload }) =>
			adminSaasApiService.updatePlan(vars.tier, vars.payload),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.admin.saasPlans() });
			setEditingPlan(null);
			resetForm();
			toast.success("Plan updated (existing tenants grandfathered)");
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to update plan");
		},
	});

	const deleteMutation = useMutation({
		mutationFn: (tier: string) => adminSaasApiService.deletePlan(tier),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: cacheKeys.admin.saasPlans() });
			setDeletingPlanTier(null);
			toast.success("Plan tier deleted successfully");
		},
		onError: (err: unknown) => {
			toast.error(err instanceof Error ? err.message : "Failed to delete plan");
		},
	});

	const resetForm = () => {
		setFormTier("");
		setFormDocs("");
		setFormMembers("");
		setFormRuns("");
		setFormStorageGb("");
		setFormCredits("");
		setFormSources("");
		setFormSupport("email");
		setFormPriceDollars("0");
		setFormCurrency("USD");
	};

	const openEditModal = (plan: PlanDefinition) => {
		setEditingPlan(plan);
		setFormTier(plan.plan_tier);
		setFormDocs(
			plan.max_documents !== null && plan.max_documents !== undefined
				? String(plan.max_documents)
				: ""
		);
		setFormMembers(
			plan.max_members !== null && plan.max_members !== undefined ? String(plan.max_members) : ""
		);
		setFormRuns(plan.max_runs !== null && plan.max_runs !== undefined ? String(plan.max_runs) : "");
		setFormStorageGb(
			plan.max_storage_bytes !== null && plan.max_storage_bytes !== undefined
				? String(Math.round(plan.max_storage_bytes / 1_000_000_000))
				: ""
		);
		setFormCredits(
			plan.max_monthly_credits !== null && plan.max_monthly_credits !== undefined
				? String(plan.max_monthly_credits)
				: ""
		);
		setFormSources(
			plan.max_sources !== null && plan.max_sources !== undefined ? String(plan.max_sources) : ""
		);
		setFormSupport(plan.support_level || "email");
		setFormPriceDollars(
			plan.price_micros !== null && plan.price_micros !== undefined
				? String(plan.price_micros / 1_000_000)
				: "0"
		);
		setFormCurrency(plan.currency || "USD");
	};

	const handleCreateSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!formTier.trim()) {
			toast.error("Please enter a plan tier name");
			return;
		}

		const priceDollars = parseFloat(formPriceDollars) || 0;
		const payload: CreatePlanPayload = {
			plan_tier: formTier.trim().toLowerCase(),
			max_documents: formDocs ? parseInt(formDocs, 10) : null,
			max_members: formMembers ? parseInt(formMembers, 10) : null,
			max_runs: formRuns ? parseInt(formRuns, 10) : null,
			max_storage_bytes: formStorageGb ? parseInt(formStorageGb, 10) * 1_000_000_000 : null,
			max_monthly_credits: formCredits ? parseInt(formCredits, 10) : null,
			max_sources: formSources ? parseInt(formSources, 10) : null,
			support_level: formSupport,
			price_micros: Math.round(priceDollars * 1_000_000),
			currency: formCurrency,
		};

		createMutation.mutate(payload);
	};

	const handleUpdateSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!editingPlan) return;

		const priceDollars = parseFloat(formPriceDollars) || 0;
		const payload: UpdatePlanPayload = {
			max_documents: formDocs ? parseInt(formDocs, 10) : null,
			max_members: formMembers ? parseInt(formMembers, 10) : null,
			max_runs: formRuns ? parseInt(formRuns, 10) : null,
			max_storage_bytes: formStorageGb ? parseInt(formStorageGb, 10) * 1_000_000_000 : null,
			max_monthly_credits: formCredits ? parseInt(formCredits, 10) : null,
			max_sources: formSources ? parseInt(formSources, 10) : null,
			support_level: formSupport,
			price_micros: Math.round(priceDollars * 1_000_000),
			currency: formCurrency,
		};

		updateMutation.mutate({ tier: editingPlan.plan_tier, payload });
	};

	return (
		<div className="p-6 max-w-7xl mx-auto space-y-6">
			<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
				<div>
					<h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
						<Layers className="h-6 w-6 text-primary" />
						SaaS Plan Catalog
					</h1>
					<p className="text-sm text-muted-foreground mt-1">
						Manage platform subscription tiers, resource quotas, support levels, and grandfathering
						protection.
					</p>
				</div>
				<Button
					onClick={() => {
						resetForm();
						setIsCreateOpen(true);
					}}
				>
					<Plus className="mr-2 h-4 w-4" />
					Create Plan Tier
				</Button>
			</div>

			<Card>
				<CardHeader className="pb-3">
					<CardTitle className="text-base font-semibold">Active Plan Tiers</CardTitle>
					<CardDescription className="text-xs">
						System default tiers (Free, Team, Growth, Enterprise) cannot be deleted. Modifying
						defaults preserves existing tenant quotas via grandfathered overrides.
					</CardDescription>
				</CardHeader>
				<CardContent>
					{isLoading ? (
						<div className="space-y-3">
							<Skeleton className="h-10 w-full" />
							<Skeleton className="h-10 w-full" />
							<Skeleton className="h-10 w-full" />
						</div>
					) : !plans || plans.length === 0 ? (
						<p className="text-sm text-muted-foreground py-6 text-center">
							No SaaS plans found in the catalog.
						</p>
					) : (
						<div className="rounded-md border overflow-x-auto">
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead>Plan Tier</TableHead>
										<TableHead>Type</TableHead>
										<TableHead>Price / Mo</TableHead>
										<TableHead>Support</TableHead>
										<TableHead>Docs</TableHead>
										<TableHead>Members</TableHead>
										<TableHead>Runs</TableHead>
										<TableHead>Storage</TableHead>
										<TableHead>Credits</TableHead>
										<TableHead className="text-right">Actions</TableHead>
									</TableRow>
								</TableHeader>
								<TableBody>
									{plans.map((plan) => (
										<TableRow key={plan.plan_tier}>
											<TableCell className="font-semibold uppercase tracking-wide text-xs">
												{plan.plan_tier}
											</TableCell>
											<TableCell>
												{plan.is_system_default ? (
													<Badge variant="secondary" className="text-[10px] gap-1">
														<ShieldCheck className="h-3 w-3 text-primary" />
														System
													</Badge>
												) : (
													<Badge variant="outline" className="text-[10px]">
														Custom
													</Badge>
												)}
											</TableCell>
											<TableCell className="font-medium text-xs">
												{formatCurrency(plan.price_micros, plan.currency)}
											</TableCell>
											<TableCell className="capitalize text-xs">
												{plan.support_level || "Community"}
											</TableCell>
											<TableCell className="text-xs">{plan.max_documents ?? "Unlimited"}</TableCell>
											<TableCell className="text-xs">{plan.max_members ?? "Unlimited"}</TableCell>
											<TableCell className="text-xs">{plan.max_runs ?? "Unlimited"}</TableCell>
											<TableCell className="text-xs">
												{formatBytes(plan.max_storage_bytes)}
											</TableCell>
											<TableCell className="text-xs">
												{plan.max_monthly_credits ? `${plan.max_monthly_credits}/mo` : "Standard"}
											</TableCell>
											<TableCell className="text-right space-x-1">
												<Button
													variant="ghost"
													size="icon"
													className="h-8 w-8 text-muted-foreground hover:text-foreground"
													onClick={() => openEditModal(plan)}
												>
													<Edit className="h-4 w-4" />
												</Button>
												{!plan.is_system_default && (
													<Button
														variant="ghost"
														size="icon"
														className="h-8 w-8 text-destructive hover:text-destructive"
														onClick={() => setDeletingPlanTier(plan.plan_tier)}
													>
														<Trash2 className="h-4 w-4" />
													</Button>
												)}
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					)}
				</CardContent>
			</Card>

			{/* Create Plan Dialog */}
			<Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
				<DialogContent className="max-w-xl">
					<DialogHeader>
						<DialogTitle>Create New SaaS Plan</DialogTitle>
						<DialogDescription>
							Define a new plan tier with default limits and pricing for tenants.
						</DialogDescription>
					</DialogHeader>

					<form onSubmit={handleCreateSubmit} className="space-y-4 py-2">
						<div className="grid grid-cols-2 gap-4">
							<div className="space-y-1.5">
								<Label htmlFor="create-tier">Plan Tier Name</Label>
								<Input
									id="create-tier"
									placeholder="e.g. enterprise_plus"
									value={formTier}
									onChange={(e) => setFormTier(e.target.value)}
									required
								/>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="create-support">Support Level</Label>
								<Select value={formSupport} onValueChange={setFormSupport}>
									<SelectTrigger id="create-support">
										<SelectValue placeholder="Select support level" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="community">Community</SelectItem>
										<SelectItem value="email">Email</SelectItem>
										<SelectItem value="priority">Priority</SelectItem>
										<SelectItem value="dedicated_24_7">Dedicated 24/7</SelectItem>
									</SelectContent>
								</Select>
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div className="space-y-1.5">
								<Label htmlFor="create-price">Price / Month ($)</Label>
								<Input
									id="create-price"
									type="number"
									min="0"
									step="1"
									value={formPriceDollars}
									onChange={(e) => setFormPriceDollars(e.target.value)}
								/>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="create-currency">Currency</Label>
								<Input
									id="create-currency"
									value={formCurrency}
									onChange={(e) => setFormCurrency(e.target.value.toUpperCase())}
									maxLength={3}
								/>
							</div>
						</div>

						<div className="border-t pt-3">
							<h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
								Default Resource Quotas (Leave empty for Unlimited)
							</h4>
							<div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
								<div className="space-y-1">
									<Label htmlFor="create-docs" className="text-xs">
										Max Documents
									</Label>
									<Input
										id="create-docs"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formDocs}
										onChange={(e) => setFormDocs(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="create-members" className="text-xs">
										Max Members
									</Label>
									<Input
										id="create-members"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formMembers}
										onChange={(e) => setFormMembers(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="create-runs" className="text-xs">
										Max Runs
									</Label>
									<Input
										id="create-runs"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formRuns}
										onChange={(e) => setFormRuns(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="create-storage" className="text-xs">
										Storage (GB)
									</Label>
									<Input
										id="create-storage"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formStorageGb}
										onChange={(e) => setFormStorageGb(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="create-credits" className="text-xs">
										Monthly Credits
									</Label>
									<Input
										id="create-credits"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formCredits}
										onChange={(e) => setFormCredits(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="create-sources" className="text-xs">
										Max Sources
									</Label>
									<Input
										id="create-sources"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formSources}
										onChange={(e) => setFormSources(e.target.value)}
									/>
								</div>
							</div>
						</div>

						<DialogFooter className="pt-4">
							<Button variant="outline" type="button" onClick={() => setIsCreateOpen(false)}>
								Cancel
							</Button>
							<Button type="submit" disabled={createMutation.isPending}>
								{createMutation.isPending ? "Creating..." : "Create Plan"}
							</Button>
						</DialogFooter>
					</form>
				</DialogContent>
			</Dialog>

			{/* Edit Plan Dialog */}
			<Dialog open={Boolean(editingPlan)} onOpenChange={(open) => !open && setEditingPlan(null)}>
				<DialogContent className="max-w-xl">
					<DialogHeader>
						<DialogTitle>
							Edit Plan: <span className="uppercase text-primary">{editingPlan?.plan_tier}</span>
						</DialogTitle>
						<DialogDescription>
							Update default limits and pricing. Existing tenant workspaces on this tier will be
							grandfathered with their previous limits preserved.
						</DialogDescription>
					</DialogHeader>

					<div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-md text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
						<AlertCircle className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-400 shrink-0" />
						<span>
							Grandfathering active: Any workspace currently assigned to this tier will have its
							existing quota snapshot recorded as a per-workspace override before new defaults
							apply.
						</span>
					</div>

					<form onSubmit={handleUpdateSubmit} className="space-y-4 py-2">
						<div className="grid grid-cols-2 gap-4">
							<div className="space-y-1.5">
								<Label htmlFor="edit-support">Support Level</Label>
								<Select value={formSupport} onValueChange={setFormSupport}>
									<SelectTrigger id="edit-support">
										<SelectValue placeholder="Select support level" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="community">Community</SelectItem>
										<SelectItem value="email">Email</SelectItem>
										<SelectItem value="priority">Priority</SelectItem>
										<SelectItem value="dedicated_24_7">Dedicated 24/7</SelectItem>
									</SelectContent>
								</Select>
							</div>
							<div className="space-y-1.5">
								<Label htmlFor="edit-price">Price / Month ($)</Label>
								<Input
									id="edit-price"
									type="number"
									min="0"
									step="1"
									value={formPriceDollars}
									onChange={(e) => setFormPriceDollars(e.target.value)}
								/>
							</div>
						</div>

						<div className="border-t pt-3">
							<h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
								Default Resource Quotas (Leave empty for Unlimited)
							</h4>
							<div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
								<div className="space-y-1">
									<Label htmlFor="edit-docs" className="text-xs">
										Max Documents
									</Label>
									<Input
										id="edit-docs"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formDocs}
										onChange={(e) => setFormDocs(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="edit-members" className="text-xs">
										Max Members
									</Label>
									<Input
										id="edit-members"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formMembers}
										onChange={(e) => setFormMembers(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="edit-runs" className="text-xs">
										Max Runs
									</Label>
									<Input
										id="edit-runs"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formRuns}
										onChange={(e) => setFormRuns(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="edit-storage" className="text-xs">
										Storage (GB)
									</Label>
									<Input
										id="edit-storage"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formStorageGb}
										onChange={(e) => setFormStorageGb(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="edit-credits" className="text-xs">
										Monthly Credits
									</Label>
									<Input
										id="edit-credits"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formCredits}
										onChange={(e) => setFormCredits(e.target.value)}
									/>
								</div>
								<div className="space-y-1">
									<Label htmlFor="edit-sources" className="text-xs">
										Max Sources
									</Label>
									<Input
										id="edit-sources"
										type="number"
										min="0"
										placeholder="Unlimited"
										value={formSources}
										onChange={(e) => setFormSources(e.target.value)}
									/>
								</div>
							</div>
						</div>

						<DialogFooter className="pt-4">
							<Button variant="outline" type="button" onClick={() => setEditingPlan(null)}>
								Cancel
							</Button>
							<Button type="submit" disabled={updateMutation.isPending}>
								{updateMutation.isPending ? "Saving..." : "Save Changes"}
							</Button>
						</DialogFooter>
					</form>
				</DialogContent>
			</Dialog>

			{/* Delete Confirmation Dialog */}
			<Dialog
				open={Boolean(deletingPlanTier)}
				onOpenChange={(open) => !open && setDeletingPlanTier(null)}
			>
				<DialogContent className="max-w-sm">
					<DialogHeader>
						<DialogTitle>Delete Plan Tier</DialogTitle>
						<DialogDescription className="text-xs">
							Are you sure you want to delete tier{" "}
							<strong className="uppercase">{deletingPlanTier}</strong>? This operation cannot be
							undone. Plans assigned to active workspaces cannot be deleted.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="gap-2 sm:gap-0">
						<Button variant="outline" onClick={() => setDeletingPlanTier(null)}>
							Cancel
						</Button>
						<Button
							variant="destructive"
							disabled={deleteMutation.isPending}
							onClick={() => {
								if (deletingPlanTier) {
									deleteMutation.mutate(deletingPlanTier);
								}
							}}
						>
							{deleteMutation.isPending ? "Deleting..." : "Delete Plan"}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}
