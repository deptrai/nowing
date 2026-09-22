"use client";

import { KeyRound, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import type React from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
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

interface MfaConfirmDialogProps {
	isOpen: boolean;
	onClose: () => void;
	onConfirm: (auth: { password?: string; mfa_token?: string }) => void;
	isLoading?: boolean;
}

export function MfaConfirmDialog({
	isOpen,
	onClose,
	onConfirm,
	isLoading = false,
}: MfaConfirmDialogProps) {
	const t = useTranslations("bulkOps");
	const [password, setPassword] = useState("");
	const [mfaToken, setMfaToken] = useState("");

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		onConfirm({
			password: password.trim() || undefined,
			mfa_token: mfaToken.trim() || undefined,
		});
	};

	const isValid = password.trim().length > 0 || mfaToken.trim().length === 6;

	return (
		<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
			<DialogContent className="sm:max-w-[425px]">
				<form onSubmit={handleSubmit}>
					<DialogHeader>
						<div className="flex items-center gap-2 text-destructive">
							<ShieldAlert className="h-5 w-5" />
							<DialogTitle>{t("reauth_title")}</DialogTitle>
						</div>
						<DialogDescription className="text-xs pt-1">{t("mfa_description")}</DialogDescription>
					</DialogHeader>

					<div className="space-y-4 py-4">
						<div className="space-y-2">
							<Label htmlFor="auth-password" className="text-sm font-medium">
								{t("account_password")}
							</Label>
							<Input
								id="auth-password"
								type="password"
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								placeholder={t("password_placeholder")}
								autoComplete="current-password"
								disabled={isLoading}
							/>
						</div>

						<div className="relative flex py-1 items-center">
							<div className="flex-grow border-t border-muted" />
							<span className="flex-shrink mx-4 text-xs uppercase tracking-widest text-muted-foreground font-semibold">
								{t("or_divider")}
							</span>
							<div className="flex-grow border-t border-muted" />
						</div>

						<div className="space-y-2">
							<Label htmlFor="auth-mfa" className="text-sm font-medium flex items-center gap-1.5">
								<KeyRound className="h-3.5 w-3.5" />
								{t("mfa_code_label")}
							</Label>
							<Input
								id="auth-mfa"
								type="text"
								maxLength={6}
								value={mfaToken}
								onChange={(e) => setMfaToken(e.target.value.replace(/\D/g, ""))}
								placeholder="123456"
								className="font-mono text-center tracking-widest text-base"
								disabled={isLoading}
							/>
						</div>
					</div>

					<DialogFooter className="gap-2 sm:gap-0">
						<Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
							{t("cancel")}
						</Button>
						<Button type="submit" variant="destructive" disabled={!isValid || isLoading}>
							{isLoading ? t("verifying") : t("confirm_execute")}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
