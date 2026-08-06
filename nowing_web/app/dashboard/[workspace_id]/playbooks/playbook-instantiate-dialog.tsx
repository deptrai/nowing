"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { instantiatePlaybookMutationAtom } from "@/atoms/playbooks/playbooks-mutation.atoms";
import { SchemaForm } from "@/components/schema-form/schema-form";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import type { PlaybookSummary } from "@/contracts/types/playbook.types";
import { playbooksApiService } from "@/lib/apis/playbooks-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface PlaybookInstantiateDialogProps {
	playbook: PlaybookSummary;
	workspaceId: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

/**
 * Opens a schema-driven form for a playbook's ``inputs.schema`` and creates an
 * automation on submit.  If the playbook has no inputs schema the dialog
 * becomes a simple confirmation.
 */
export function PlaybookInstantiateDialog({
	playbook,
	workspaceId,
	open,
	onOpenChange,
}: PlaybookInstantiateDialogProps) {
	const router = useRouter();
	const { mutateAsync: instantiate, isPending } = useAtomValue(instantiatePlaybookMutationAtom);
	const [instantiateError, setInstantiateError] = useState<string | null>(null);

	const { data: detail, isLoading } = useQuery({
		queryKey: [...cacheKeys.playbooks.detail(playbook.id)],
		queryFn: () => playbooksApiService.getPlaybook(playbook.id),
		enabled: open,
	});

	const inputsSchema = detail?.inputs_schema as Record<string, unknown> | undefined;
	const hasInputs = !!(
		typeof inputsSchema === "object" &&
		inputsSchema !== null &&
		"properties" in inputsSchema &&
		Object.keys((inputsSchema as { properties?: Record<string, unknown> }).properties ?? {})
			.length > 0
	);

	async function handleSubmit(values?: Record<string, unknown>) {
		setInstantiateError(null);
		try {
			const automation = await instantiate({
				playbookId: playbook.id,
				request: {
					workspace_id: workspaceId,
					inputs: hasInputs ? (values ?? {}) : {},
				},
			});
			onOpenChange(false);
			router.push(`/dashboard/${workspaceId}/automations/${automation.id}`);
		} catch (err) {
			setInstantiateError((err as Error).message ?? "Failed to instantiate playbook");
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[90vh] overflow-y-auto">
				<DialogHeader>
					<DialogTitle>Run {playbook.name}</DialogTitle>
					<DialogDescription>
						{hasInputs
							? "Fill in the inputs below to create an automation from this playbook."
							: "Run this playbook now?"}
					</DialogDescription>
				</DialogHeader>

				{isLoading ? (
					<div className="flex justify-center py-8">
						<Spinner />
					</div>
				) : hasInputs && inputsSchema ? (
					<SchemaForm
						// biome-ignore lint/suspicious/noExplicitAny: JSON Schema is dynamic.
						schema={inputsSchema as any}
						onSubmit={handleSubmit}
						submitLabel={isPending ? "Running..." : "Run playbook"}
					/>
				) : (
					<div className="space-y-4">
						{instantiateError && <p className="text-sm text-destructive">{instantiateError}</p>}
						<DialogFooter>
							<Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
								Cancel
							</Button>
							<Button type="button" onClick={() => handleSubmit()} disabled={isPending}>
								{isPending ? "Running..." : "Run playbook"}
							</Button>
						</DialogFooter>
					</div>
				)}

				{hasInputs && instantiateError && (
					<p className="text-sm text-destructive pt-2">{instantiateError}</p>
				)}
			</DialogContent>
		</Dialog>
	);
}
