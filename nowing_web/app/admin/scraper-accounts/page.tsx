"use client";

import { useAtom } from "jotai";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
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
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type {
	ScraperPlatformAccount,
	ScraperPlatformAccountCredentials,
} from "@/lib/apis/scraper-platform-accounts-api.service";
import { scraperPlatformAccountsApiService } from "@/lib/apis/scraper-platform-accounts-api.service";

const PLATFORM_OPTIONS = [
	{ value: "muaban_bds", label: "Muaban BĐS" },
	{ value: "batdongsan", label: "Batdongsan.com.vn" },
	{ value: "chotot_bds", label: "Chotot BĐS" },
];

interface AccountForm {
	platform: string;
	label: string;
	is_enabled: boolean;
	is_default: boolean;
	cookies: string;
	token: string;
}

const emptyForm: AccountForm = {
	platform: "",
	label: "",
	is_enabled: true,
	is_default: false,
	cookies: "",
	token: "",
};

function toForm(account: ScraperPlatformAccount): AccountForm {
	const creds = account.credentials ?? {};
	return {
		platform: account.platform,
		label: account.label ?? "",
		is_enabled: account.is_enabled,
		is_default: account.is_default,
		cookies: creds.cookies ?? "",
		token: creds.token ?? "",
	};
}

function fromForm(form: AccountForm): {
	platform: string;
	label: string | null;
	is_enabled: boolean;
	is_default: boolean;
	credentials: ScraperPlatformAccountCredentials | null;
} {
	return {
		platform: form.platform,
		label: form.label.trim() || null,
		is_enabled: form.is_enabled,
		is_default: form.is_default,
		credentials:
			form.cookies.trim() || form.token.trim()
				? {
						cookies: form.cookies.trim() || null,
						token: form.token.trim() || null,
					}
				: null,
	};
}

export default function ScraperAccountsAdminPage() {
	const [{ data: user, isLoading: userLoading }] = useAtom(currentUserAtom);
	const [accounts, setAccounts] = useState<ScraperPlatformAccount[]>([]);
	const [listLoading, setListLoading] = useState(true);
	const [createOpen, setCreateOpen] = useState(false);
	const [draft, setDraft] = useState<AccountForm>(emptyForm);
	const [editDialog, setEditDialog] = useState<{
		open: boolean;
		account: ScraperPlatformAccount | null;
		draft: AccountForm;
	}>({ open: false, account: null, draft: emptyForm });
	const [deleteDialog, setDeleteDialog] = useState<ScraperPlatformAccount | null>(null);

	const isSuperuser = user?.is_superuser ?? false;

	const load = async () => {
		setListLoading(true);
		try {
			const data = await scraperPlatformAccountsApiService.list();
			setAccounts(data);
		} catch {
			toast.error("Failed to load scraper accounts");
		} finally {
			setListLoading(false);
		}
	};

	useEffect(() => {
		if (isSuperuser) {
			void load();
		}
	}, [isSuperuser]);

	useEffect(() => {
		if (!createOpen) {
			setDraft(emptyForm);
		}
	}, [createOpen]);

	const isCreateValid = useMemo(() => draft.platform.trim().length > 0, [draft.platform]);

	async function handleCreate() {
		if (!isCreateValid) return;
		try {
			await scraperPlatformAccountsApiService.create(fromForm(draft));
			setCreateOpen(false);
			toast.success("Account created");
			await load();
		} catch {
			toast.error("Failed to create account");
		}
	}

	async function handleUpdate() {
		if (!editDialog.account) return;
		try {
			await scraperPlatformAccountsApiService.update(
				editDialog.account.id,
				fromForm(editDialog.draft)
			);
			setEditDialog({ open: false, account: null, draft: emptyForm });
			toast.success("Account updated");
			await load();
		} catch {
			toast.error("Failed to update account");
		}
	}

	async function handleDelete() {
		if (!deleteDialog) return;
		try {
			await scraperPlatformAccountsApiService.delete(deleteDialog.id);
			toast.success("Account deleted");
			await load();
		} catch {
			toast.error("Failed to delete account");
		} finally {
			setDeleteDialog(null);
		}
	}

	async function handleToggleEnabled(account: ScraperPlatformAccount) {
		try {
			await scraperPlatformAccountsApiService.update(account.id, {
				is_enabled: !account.is_enabled,
			});
			toast.success("Account updated");
			await load();
		} catch {
			toast.error("Failed to update account");
		}
	}

	function openEdit(account: ScraperPlatformAccount) {
		setEditDialog({ open: true, account, draft: toForm(account) });
	}

	if (userLoading) {
		return (
			<div className="flex h-full items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (!isSuperuser) {
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
					<h1 className="text-2xl font-semibold">Scraper platform accounts</h1>
					<p className="text-sm text-muted-foreground">
						Manage cookies, tokens and API credentials for scraper platforms.
					</p>
				</div>
				<Button onClick={() => setCreateOpen(true)}>Add account</Button>
			</div>

			{listLoading ? (
				<div className="flex h-64 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : accounts.length === 0 ? (
				<Card>
					<CardContent className="flex h-40 items-center justify-center text-muted-foreground">
						No scraper platform accounts found.
					</CardContent>
				</Card>
			) : (
				<div className="space-y-4">
					{accounts.map((account) => (
						<Card key={account.id}>
							<CardHeader className="pb-3">
								<div className="flex items-start justify-between gap-4">
									<div>
										<CardTitle>
											{account.label || account.platform}
											{account.is_default && (
												<span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
													Default
												</span>
											)}
										</CardTitle>
										<CardDescription>{account.platform}</CardDescription>
									</div>
									<div className="flex items-center gap-2">
										<span className="text-sm text-muted-foreground">
											{account.is_enabled ? "Enabled" : "Disabled"}
										</span>
										<Switch
											checked={account.is_enabled}
											onCheckedChange={() => handleToggleEnabled(account)}
										/>
										<Button variant="outline" size="sm" onClick={() => openEdit(account)}>
											Edit
										</Button>
										<Button variant="outline" size="sm" onClick={() => setDeleteDialog(account)}>
											Delete
										</Button>
									</div>
								</div>
							</CardHeader>
							<CardContent className="space-y-2 text-sm">
								<p className="text-muted-foreground">
									Created: {new Date(account.created_at).toLocaleString()}
								</p>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			<Dialog open={createOpen} onOpenChange={setCreateOpen}>
				<DialogContent className="max-w-xl">
					<DialogHeader>
						<DialogTitle>Add scraper account</DialogTitle>
						<DialogDescription>
							Paste the browser cookie string or token the scraper should use.
						</DialogDescription>
					</DialogHeader>
					<AccountFormFields form={draft} setForm={(next) => setDraft(next(draft))} />
					<DialogFooter>
						<Button variant="outline" onClick={() => setCreateOpen(false)}>
							Cancel
						</Button>
						<Button onClick={handleCreate} disabled={!isCreateValid}>
							Save
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<Dialog
				open={editDialog.open}
				onOpenChange={(open) => {
					if (!open) setEditDialog({ open: false, account: null, draft: emptyForm });
				}}
			>
				<DialogContent className="max-w-xl">
					<DialogHeader>
						<DialogTitle>Edit scraper account</DialogTitle>
						<DialogDescription>Update credentials for this platform.</DialogDescription>
					</DialogHeader>
					<AccountFormFields
						form={editDialog.draft}
						setForm={(next) => setEditDialog((prev) => ({ ...prev, draft: next(prev.draft) }))}
					/>
					<DialogFooter>
						<Button
							variant="outline"
							onClick={() => setEditDialog({ open: false, account: null, draft: emptyForm })}
						>
							Cancel
						</Button>
						<Button onClick={handleUpdate}>Save</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			<Dialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
				<DialogContent className="max-w-md">
					<DialogHeader>
						<DialogTitle>Delete account</DialogTitle>
						<DialogDescription>
							Are you sure you want to delete this account? This action cannot be undone.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter>
						<Button variant="outline" onClick={() => setDeleteDialog(null)}>
							Cancel
						</Button>
						<Button variant="destructive" onClick={handleDelete}>
							Delete
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</div>
	);
}

function AccountFormFields({
	form,
	setForm,
}: {
	form: AccountForm;
	setForm: (fn: (prev: AccountForm) => AccountForm) => void;
}) {
	function update<K extends keyof AccountForm>(key: K, value: AccountForm[K]) {
		setForm((prev) => ({ ...prev, [key]: value }));
	}

	return (
		<div className="space-y-4 py-4">
			<div className="space-y-2">
				<Label>Platform</Label>
				<Select value={form.platform} onValueChange={(v) => update("platform", v)}>
					<SelectTrigger>
						<SelectValue placeholder="Select a platform" />
					</SelectTrigger>
					<SelectContent>
						{PLATFORM_OPTIONS.map((opt) => (
							<SelectItem key={opt.value} value={opt.value}>
								{opt.label}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>

			<div className="space-y-2">
				<Label>Label</Label>
				<Input
					value={form.label}
					onChange={(e) => update("label", e.target.value)}
					placeholder="e.g. Production muaban account"
				/>
			</div>

			<div className="flex items-center gap-6">
				<div className="flex items-center gap-2">
					<Switch
						checked={form.is_enabled}
						onCheckedChange={(v) => update("is_enabled", v)}
						id="edit-enabled"
					/>
					<Label htmlFor="edit-enabled">Enabled</Label>
				</div>
				<div className="flex items-center gap-2">
					<Switch
						checked={form.is_default}
						onCheckedChange={(v) => update("is_default", v)}
						id="edit-default"
					/>
					<Label htmlFor="edit-default">Default</Label>
				</div>
			</div>

			<div className="space-y-2">
				<Label>Browser cookie string</Label>
				<textarea
					value={form.cookies}
					onChange={(e) => update("cookies", e.target.value)}
					placeholder="Paste document.cookie here"
					className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
				/>
			</div>

			<div className="space-y-2">
				<Label>Token</Label>
				<Input
					type="password"
					value={form.token}
					onChange={(e) => update("token", e.target.value)}
					placeholder="API token if the platform supports one"
				/>
			</div>
		</div>
	);
}
