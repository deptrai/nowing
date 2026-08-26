"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { userApiService } from "@/lib/apis/user-api.service";

export function PasswordContent() {
	const t = useTranslations("userSettings");

	const [currentPassword, setCurrentPassword] = useState("");
	const [newPassword, setNewPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [isPending, setIsPending] = useState(false);

	const hasChanges =
		currentPassword.length > 0 && newPassword.length >= 8 && confirmPassword.length > 0;
	const canSubmit =
		hasChanges && newPassword === confirmPassword && newPassword !== currentPassword;

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		if (newPassword !== confirmPassword) {
			toast.error(t("password_mismatch"));
			return;
		}

		if (newPassword.length < 8) {
			toast.error(t("password_too_short"));
			return;
		}

		setIsPending(true);
		try {
			await userApiService.changePassword({
				current_password: currentPassword,
				new_password: newPassword,
			});
			toast.success(t("password_saved"));
			setCurrentPassword("");
			setNewPassword("");
			setConfirmPassword("");
		} catch {
			toast.error(t("password_save_error"));
		} finally {
			setIsPending(false);
		}
	};

	return (
		<div>
			<form onSubmit={handleSubmit} className="space-y-6">
				<div className="rounded-lg bg-main-panel">
					<div className="flex flex-col gap-6">
						<div className="space-y-2">
							<Label htmlFor="current-password">{t("current_password")}</Label>
							<Input
								id="current-password"
								type="password"
								autoComplete="current-password"
								value={currentPassword}
								onChange={(e) => setCurrentPassword(e.target.value)}
							/>
						</div>

						<div className="space-y-2">
							<Label htmlFor="new-password">{t("new_password")}</Label>
							<Input
								id="new-password"
								type="password"
								autoComplete="new-password"
								value={newPassword}
								onChange={(e) => setNewPassword(e.target.value)}
							/>
							<p className="text-xs text-muted-foreground">{t("new_password_hint")}</p>
						</div>

						<div className="space-y-2">
							<Label htmlFor="confirm-password">{t("confirm_password")}</Label>
							<Input
								id="confirm-password"
								type="password"
								autoComplete="new-password"
								value={confirmPassword}
								onChange={(e) => setConfirmPassword(e.target.value)}
							/>
						</div>

						{newPassword && confirmPassword && newPassword !== confirmPassword && (
							<p className="text-sm text-destructive">{t("password_mismatch")}</p>
						)}
					</div>
				</div>

				<div className="flex justify-end">
					<Button
						type="submit"
						variant="outline"
						disabled={!canSubmit || isPending}
						className="relative gap-2 bg-white text-black hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-black"
					>
						<span className={isPending ? "opacity-0" : ""}>{t("password_save")}</span>
						{isPending && <Spinner size="sm" className="absolute" />}
					</Button>
				</div>
			</form>
		</div>
	);
}
