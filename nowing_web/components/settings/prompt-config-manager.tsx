"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { AlertTriangle, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { updateWorkspaceMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface PromptConfigManagerProps {
	workspaceId: number;
}

export function PromptConfigManager({ workspaceId }: PromptConfigManagerProps) {
	const t = useTranslations("settings");
	const { data: workspace, isLoading: loading } = useQuery({
		queryKey: cacheKeys.workspaces.detail(workspaceId.toString()),
		queryFn: () => workspacesApiService.getWorkspace({ id: workspaceId }),
		enabled: !!workspaceId,
	});

	const { mutateAsync: updateWorkspace, isPending: isSaving } = useAtomValue(
		updateWorkspaceMutationAtom
	);

	const [customInstructions, setCustomInstructions] = useState("");
	const hasWorkspace = !!workspace;
	const workspaceInstructions = workspace?.qna_custom_instructions;

	// Initialize state from fetched workspace
	useEffect(() => {
		if (hasWorkspace) {
			setCustomInstructions(workspaceInstructions || "");
		}
	}, [hasWorkspace, workspaceInstructions]);

	// Derive hasChanges during render
	const hasChanges =
		!!workspace && (workspace.qna_custom_instructions || "") !== customInstructions;

	const handleSave = async () => {
		try {
			await updateWorkspace({
				id: workspaceId,
				data: { qna_custom_instructions: customInstructions.trim() || "" },
			});
			toast.success(t("instructions_saved"));
		} catch (error: unknown) {
			const message = error instanceof Error ? error.message : t("instructions_save_failed");
			console.error("Error saving system instructions:", error);
			toast.error(message);
		}
	};

	const onSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		handleSave();
	};

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<div className="space-y-3 md:space-y-4">
					<div className="space-y-2">
						<Skeleton className="h-5 md:h-6 w-36 md:w-48" aria-hidden="true" />
						<Skeleton className="h-3 md:h-4 w-full max-w-md mt-2" />
					</div>
					<div className="space-y-3 md:space-y-4">
						<Skeleton className="h-16 md:h-20 w-full" />
						<Skeleton className="h-24 md:h-32 w-full" />
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Work in Progress Notice */}
			<Alert variant="warning">
				<AlertTriangle />
				<AlertTitle>{t("wip_title")}</AlertTitle>
				<AlertDescription>{t("wip_desc")}</AlertDescription>
			</Alert>

			<Alert>
				<Info />
				<AlertDescription>{t("instructions_info")}</AlertDescription>
			</Alert>

			{/* System Instructions Card */}
			<form onSubmit={onSubmit} className="space-y-4 md:space-y-6">
				<div className="space-y-3 md:space-y-4">
					<div className="space-y-1.5 md:space-y-2">
						<h3 className="text-base md:text-lg font-semibold tracking-tight">
							{t("custom_instructions")}
						</h3>
						<p className="text-xs md:text-sm text-muted-foreground">
							{t("custom_instructions_desc")}
						</p>
					</div>
					<div className="space-y-3 md:space-y-4">
						<div className="space-y-1.5 md:space-y-2">
							<Label
								htmlFor="custom-instructions-settings"
								className="text-sm md:text-base font-medium"
							>
								{t("your_instructions")}
							</Label>
							<Textarea
								id="custom-instructions-settings"
								placeholder={t("instructions_placeholder")}
								value={customInstructions}
								onChange={(e) => setCustomInstructions(e.target.value)}
								rows={10}
								className="resize-none font-mono text-xs md:text-sm"
							/>
							<div className="flex items-center justify-between">
								<p className="text-[10px] md:text-xs text-muted-foreground">
									{t("characters_count", { count: customInstructions.length })}
								</p>
								{customInstructions.length > 0 && (
									<Button
										type="button"
										variant="ghost"
										size="sm"
										onClick={() => setCustomInstructions("")}
										className="h-auto py-0.5 md:py-1 px-1.5 md:px-2 text-[10px] md:text-xs"
									>
										{t("clear")}
									</Button>
								)}
							</div>
						</div>

						{customInstructions.trim().length === 0 && (
							<Alert>
								<Info />
								<AlertDescription>{t("no_instructions")}</AlertDescription>
							</Alert>
						)}
					</div>
				</div>

				{/* Action Buttons */}
				<div className="flex justify-end pt-3 md:pt-4">
					<Button
						type="submit"
						variant="outline"
						disabled={!hasChanges || isSaving}
						className="gap-2 bg-white text-black hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-black"
					>
						{isSaving ? <Spinner size="sm" /> : null}
						{isSaving ? t("saving") : t("save_instructions")}
					</Button>
				</div>
			</form>
		</div>
	);
}
