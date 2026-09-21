"use client";
import { useAtomValue } from "jotai";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { deleteAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Spinner } from "@/components/ui/spinner";

interface DeleteAutomationDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	automationId: number;
	automationName: string;
	workspaceId: number;
	/**
	 * Fired after a successful delete, before the dialog closes. The detail
	 * page uses this to navigate back to the list (the row simply vanishes
	 * on the list page so no callback is needed there).
	 */
	onDeleted?: () => void;
}

/**
 * Confirm + delete one automation. FK cascade on the backend wipes attached
 * triggers and runs, so we mention it explicitly. List re-fetch is handled
 * by the mutation atom's onSuccess.
 */
export function DeleteAutomationDialog({
	open,
	onOpenChange,
	automationId,
	automationName,
	workspaceId,
	onDeleted,
}: DeleteAutomationDialogProps) {
	const t = useTranslations("automations");
	const { mutateAsync: deleteAutomation } = useAtomValue(deleteAutomationMutationAtom);
	const [submitting, setSubmitting] = useState(false);

	async function handleConfirm() {
		setSubmitting(true);
		try {
			await deleteAutomation({ automationId, workspaceId: workspaceId });
			onDeleted?.();
			onOpenChange(false);
		} finally {
			setSubmitting(false);
		}
	}

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>{t("auto_delete_this_automation")}</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{automationName}</span> and all of its
						triggers and run history will be removed. This cannot be undone.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<AlertDialogFooter>
					<AlertDialogCancel disabled={submitting}>{t("cancel")}</AlertDialogCancel>
					<AlertDialogAction
						onClick={handleConfirm}
						disabled={submitting}
						className="bg-destructive text-white hover:bg-destructive/90"
					>
						{submitting ? (
							<span className="inline-flex items-center gap-2">
								<Spinner size="xs" />
								{t("auto_deleting")}
							</span>
						) : (
							t("auto_delete")
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
