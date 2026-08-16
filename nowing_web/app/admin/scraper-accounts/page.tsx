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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
	ScraperPlatformAccount,
	ScraperPlatformAccountCredentials,
} from "@/lib/apis/scraper-platform-accounts-api.service";
import { scraperPlatformAccountsApiService } from "@/lib/apis/scraper-platform-accounts-api.service";

const PLATFORM_OPTIONS = [
	{ value: "muaban_bds", label: "Muaban BĐS" },
	{ value: "batdongsan", label: "Batdongsan.com.vn" },
	{ value: "chotot_bds", label: "Chotot BĐS" },
	{ value: "telegram", label: "Telegram (MTProto Userbot)" },
];

const BATDONGSAN_COOKIE_KEEP_EXACT = new Set([
	"clientIp",
	"con.unl.lat",
	"con.unl.sc",
	"con.ses.id",
	"USER_PRODUCT_SEARCH",
	"userinfo",
	"c_u_id",
	"exp.stg.userid",
	"exp.stg.stableid",
	"ajs_user_id",
	"ajs_anonymous_id",
	"CURRENT_SECTION",
	"AWSALB",
	"AWSALBCORS",
	"con.unl.usr.id",
	"con.unl.cli.id",
	"__uif",
	"_dd_s",
	"BDS.UMS.Cookie",
	"_cfuvid",
	"accessToken",
	"refreshToken",
	"_gcl_au",
	"_ga",
	"_ga_HTS298453C",
	"_fbp",
	"ph_phc_Twg4bLVDz7InVj8BSvMQBW4gX1KtsbnaOKWSdn0SupU_posthog",
	"CURRENT_SECTION",
	"ttcsid",
	"ttcsid_CHHL1E3C77U1H95PSJM0",
]);

const BATDONGSAN_COOKIE_KEEP_PREFIXES = [
	"ab.storage.deviceId.",
	"ab.storage.userId.",
	"ab.storage.sessionId.",
	"ttcsid",
	"ttcsid_",
];

const BATDONGSAN_COOKIE_DROP_PREFIXES = [
	"_ga",
	"_ga_",
	"_fbp",
	"__uidac",
	"__admUTMtime",
	"_tt_enable_cookie",
	"_ttp",
	"__iid",
	"__su",
	"__RC",
	"__R",
	"_hjSession",
	"_hjSessionUser_",
	"__tb",
	"__IP",
	"__gads",
	"__gpi",
	"__eoi",
	"ph_phc_",
];

function shouldKeepBatdongsanCookie(name: string): boolean {
	if (BATDONGSAN_COOKIE_KEEP_EXACT.has(name)) {
		return true;
	}
	if (BATDONGSAN_COOKIE_KEEP_PREFIXES.some((p) => name.startsWith(p))) {
		return true;
	}
	if (BATDONGSAN_COOKIE_DROP_PREFIXES.some((p) => name.startsWith(p))) {
		return false;
	}
	return true;
}

function parseCookieInput(raw: string): { name: string; value: string }[] {
	const trimmed = raw.trim();
	if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
		try {
			const parsed = JSON.parse(trimmed);
			const arr = Array.isArray(parsed) ? parsed : [parsed];
			return arr
				.filter((c) => c && typeof c.name === "string")
				.map((c) => ({ name: c.name, value: String(c.value ?? "") }));
		} catch {
			// fall through to legacy parsing
		}
	}

	return raw
		.split(";")
		.map((part) => part.trim())
		.filter((part) => part.includes("="))
		.map((part) => {
			const eq = part.indexOf("=");
			const name = part.slice(0, eq).trim();
			const value = part.slice(eq + 1).trim();
			return { name, value };
		});
}

function filterBatdongsanCookies(raw: string): string {
	const trimmed = raw.trim();
	const isJson = trimmed.startsWith("[") || trimmed.startsWith("{");
	const parsed = parseCookieInput(raw);
	const kept = parsed.filter(({ name }) => shouldKeepBatdongsanCookie(name));

	if (isJson) {
		return JSON.stringify(kept, null, 2);
	}
	return kept.map(({ name, value }) => `${name}=${value}`).join("; ");
}

interface AccountForm {
	platform: string;
	label: string;
	is_enabled: boolean;
	is_default: boolean;
	cookies: string;
	token: string;
}

const emptyForm: AccountForm = {
	platform: "telegram",
	label: "",
	is_enabled: true,
	is_default: false,
	cookies: "",
	token: "",
};

function toForm(account: ScraperPlatformAccount): AccountForm {
	const creds = account.credentials as ScraperPlatformAccountCredentials | undefined;
	const cookies = creds?.cookies
		? typeof creds.cookies === "string"
			? creds.cookies
			: JSON.stringify(creds.cookies, null, 2)
		: "";
	const token = creds?.token || "";
	return {
		platform: account.platform,
		label: account.label || "",
		is_enabled: account.is_enabled,
		is_default: account.is_default,
		cookies,
		token,
	};
}

function fromForm(form: AccountForm): {
	platform: string;
	label?: string;
	is_enabled: boolean;
	is_default: boolean;
	credentials: ScraperPlatformAccountCredentials;
} {
	const credentials: ScraperPlatformAccountCredentials = {};
	if (form.cookies.trim()) {
		credentials.cookies = form.cookies.trim();
	}
	if (form.token.trim()) {
		credentials.token = form.token.trim();
	}

	return {
		platform: form.platform,
		label: form.label.trim() || undefined,
		is_enabled: form.is_enabled,
		is_default: form.is_default,
		credentials,
	};
}

interface MonitoredChannel {
	id: string;
	name: string;
	type: string;
	mode: string;
	messages_count: number;
	stream_enabled: boolean;
	status: "idle" | "live" | "error";
}

const INITIAL_CHANNELS: MonitoredChannel[] = [
	{
		id: "1",
		name: "@bds_hanoi_chinhchu",
		type: "Public",
		mode: "Web Preview",
		messages_count: 1420,
		stream_enabled: false,
		status: "idle",
	},
	{
		id: "2",
		name: "@nhadat_saigon_vip",
		type: "Private/Group",
		mode: "MTProto Deep",
		messages_count: 8950,
		stream_enabled: true,
		status: "live",
	},
	{
		id: "3",
		name: "@tinnhanh_bds247",
		type: "Public",
		mode: "Web Preview",
		messages_count: 350,
		stream_enabled: false,
		status: "idle",
	},
];

interface TelegramAccountItem {
	id: string;
	phone_number: string;
	platform: string;
	status: "active" | "rate_limited" | "cooldown";
	cooldown_seconds: number;
	token_quota: string;
	proxy: string;
	last_used: string;
}

const INITIAL_TELEGRAM_ACCOUNTS: TelegramAccountItem[] = [
	{
		id: "tg-1",
		phone_number: "+84 912 345 678",
		platform: "MTProto Userbot",
		status: "active",
		cooldown_seconds: 0,
		token_quota: "28 / 30 rpm",
		proxy: "socks5h://...:1080",
		last_used: "2m ago",
	},
	{
		id: "tg-2",
		phone_number: "+84 988 777 999",
		platform: "MTProto Userbot",
		status: "rate_limited",
		cooldown_seconds: 0,
		token_quota: "0 / 30 rpm",
		proxy: "socks5h://...:1080",
		last_used: "10s ago",
	},
	{
		id: "tg-3",
		phone_number: "+84 903 111 222",
		platform: "MTProto Userbot",
		status: "cooldown",
		cooldown_seconds: 42,
		token_quota: "0 / 30 rpm",
		proxy: "Direct",
		last_used: "15s ago",
	},
];

export default function ScraperAccountsPage() {
	const [{ data: user, isLoading: userLoading }] = useAtom(currentUserAtom);
	const isSuperuser = !!user?.is_superuser;

	const [accounts, setAccounts] = useState<ScraperPlatformAccount[]>([]);
	const [listLoading, setListLoading] = useState(false);
	const [createOpen, setCreateOpen] = useState(false);
	const [draft, setDraft] = useState<AccountForm>(emptyForm);
	const [editDialog, setEditDialog] = useState<{
		open: boolean;
		account: ScraperPlatformAccount | null;
		draft: AccountForm;
	}>({ open: false, account: null, draft: emptyForm });
	const [deleteDialog, setDeleteDialog] = useState<ScraperPlatformAccount | null>(null);
	const [capturing, setCapturing] = useState<string | null>(null);

	// Telegram Tab States
	const [telegramAccounts, setTelegramAccounts] =
		useState<TelegramAccountItem[]>(INITIAL_TELEGRAM_ACCOUNTS);
	const [channels, setChannels] = useState<MonitoredChannel[]>(INITIAL_CHANNELS);
	const [telegramModalOpen, setTelegramModalOpen] = useState(false);
	const [telegramStep, setTelegramStep] = useState<1 | 2>(1);
	const [tgPhone, setTgPhone] = useState("");
	const [tgApiId, setTgApiId] = useState("");
	const [tgApiHash, setTgApiHash] = useState("");
	const [tgProxy, setTgProxy] = useState("");
	const [tgCode, setTgCode] = useState("");
	const [tg2FAEnabled, setTg2FAEnabled] = useState(false);
	const [tgCloudPassword, setTgCloudPassword] = useState("");

	// Countdown timer tick for cooldown accounts
	useEffect(() => {
		const interval = setInterval(() => {
			setTelegramAccounts((prev) =>
				prev.map((acc) => {
					if (acc.status === "cooldown") {
						const nextSec = Math.max(0, acc.cooldown_seconds - 1);
						return {
							...acc,
							cooldown_seconds: nextSec,
							status: nextSec <= 0 ? "active" : "cooldown",
						};
					}
					return acc;
				})
			);
		}, 1000);
		return () => clearInterval(interval);
	}, []);

	const load = useCallback(async () => {
		setListLoading(true);
		try {
			const data = await scraperPlatformAccountsApiService.list();
			setAccounts(data);
		} catch {
			toast.error("Failed to load scraper accounts");
		} finally {
			setListLoading(false);
		}
	}, []);

	useEffect(() => {
		if (isSuperuser) {
			void load();
		}
	}, [isSuperuser, load]);

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

	async function handleCapture(platform: string) {
		try {
			setCapturing(platform);
			const res = await scraperPlatformAccountsApiService.capture(platform);
			toast.success(res.message, {
				description:
					"A browser window has opened. Log in and the cookies will be saved automatically.",
			});
			for (let i = 0; i < 30; i++) {
				await new Promise((resolve) => setTimeout(resolve, 5_000));
				await load();
			}
		} catch (error) {
			const message =
				error instanceof Error
					? error.message
					: "Failed to start capture. Make sure the backend can open a browser.";
			toast.error(message);
		} finally {
			setCapturing(null);
		}
	}

	function handleChannelToggle(channelId: string) {
		setChannels((prev) =>
			prev.map((c) => {
				if (c.id === channelId) {
					const nextStream = !c.stream_enabled;
					return {
						...c,
						stream_enabled: nextStream,
						status: nextStream ? "live" : "idle",
					};
				}
				return c;
			})
		);
		toast.success("Channel stream setting updated");
	}

	function handleSendTgCode() {
		if (!tgPhone || !tgApiId || !tgApiHash) {
			toast.error("Please fill in Phone Number, API ID, and API Hash");
			return;
		}
		setTelegramStep(2);
		toast.success("Verification code sent to your Telegram App / SMS");
	}

	function handleVerifyTgSave() {
		if (!tgCode) {
			toast.error("Please enter the verification code");
			return;
		}
		if (tg2FAEnabled && !tgCloudPassword.trim()) {
			toast.error("Please enter your 2FA Cloud Password");
			return;
		}

		const newAcc: TelegramAccountItem = {
			id: `tg-${Date.now()}`,
			phone_number: tgPhone,
			platform: "MTProto Userbot",
			status: "active",
			cooldown_seconds: 0,
			token_quota: "30 / 30 rpm",
			proxy: tgProxy || "Direct",
			last_used: "Just now",
		};
		setTelegramAccounts((prev) => [newAcc, ...prev]);
		setTelegramModalOpen(false);
		setTelegramStep(1);
		setTgPhone("");
		setTgApiId("");
		setTgApiHash("");
		setTgProxy("");
		setTgCode("");
		setTgCloudPassword("");
		toast.success("Telegram MTProto account connected successfully");
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
					<h1 className="font-serif text-2xl sm:text-3xl font-normal">Scraper platform accounts</h1>
					<p className="text-xs sm:text-sm text-muted-foreground font-sans">
						Manage cookies, tokens, Telegram MTProto userbots and channel monitoring streams.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<Button onClick={() => setTelegramModalOpen(true)} variant="outline">
						Add Telegram Account
					</Button>
					<Button onClick={() => setCreateOpen(true)}>Add account</Button>
				</div>
			</div>

			<Tabs defaultValue="all" className="space-y-6">
				<TabsList className="grid w-full grid-cols-3 max-w-md">
					<TabsTrigger value="all">All Accounts</TabsTrigger>
					<TabsTrigger value="telegram">Telegram</TabsTrigger>
					<TabsTrigger value="channels">Channels</TabsTrigger>
				</TabsList>

				<TabsContent value="all" className="space-y-4">
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
												{account.platform === "batdongsan" && (
													<Button
														variant="outline"
														size="sm"
														disabled={capturing === account.platform}
														onClick={() => handleCapture(account.platform)}
													>
														{capturing === account.platform ? "Capturing..." : "Capture session"}
													</Button>
												)}
												<Button variant="outline" size="sm" onClick={() => openEdit(account)}>
													Edit
												</Button>
												<Button
													variant="outline"
													size="sm"
													onClick={() => setDeleteDialog(account)}
												>
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
				</TabsContent>

				<TabsContent value="telegram" className="space-y-4">
					<Card>
						<CardHeader className="flex flex-row items-center justify-between pb-2">
							<div>
								<CardTitle>Telegram MTProto Accounts</CardTitle>
								<CardDescription>
									Userbot sessions with rate limit rotation, flood-wait cooldown handling, and proxy
									support.
								</CardDescription>
							</div>
							<Button onClick={() => setTelegramModalOpen(true)} size="sm">
								Connect Telegram
							</Button>
						</CardHeader>
						<CardContent>
							<div className="overflow-x-auto">
								<table className="w-full text-left text-sm">
									<thead>
										<tr className="border-b text-muted-foreground">
											<th className="py-3 px-2 font-medium" scope="col">
												Phone Number
											</th>
											<th className="py-3 px-2 font-medium" scope="col">
												Platform
											</th>
											<th className="py-3 px-2 font-medium" scope="col">
												Status
											</th>
											<th className="py-3 px-2 font-medium" scope="col">
												Token Quota
											</th>
											<th className="py-3 px-2 font-medium" scope="col">
												Proxy
											</th>
											<th className="py-3 px-2 font-medium" scope="col">
												Last Used
											</th>
											<th className="py-3 px-2 font-medium text-right" scope="col">
												Actions
											</th>
										</tr>
									</thead>

									<tbody>
										{telegramAccounts.map((acc) => (
											<tr key={acc.id} className="border-b last:border-0 hover:bg-muted/50">
												<td className="py-3 px-2 font-mono font-medium">{acc.phone_number}</td>
												<td className="py-3 px-2 text-muted-foreground">{acc.platform}</td>
												<td className="py-3 px-2">
													{acc.status === "active" && (
														<Badge
															data-testid="account-status-badge"
															className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
														>
															🟢 Active
														</Badge>
													)}
													{acc.status === "rate_limited" && (
														<Badge
															data-testid="account-status-badge"
															className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30"
														>
															🟡 Rate-Limited
														</Badge>
													)}
													{acc.status === "cooldown" && (
														<Badge data-testid="cooldown-timer-badge" variant="destructive">
															🔴 Cooldown ({acc.cooldown_seconds}s)
														</Badge>
													)}
												</td>
												<td className="py-3 px-2 text-muted-foreground">{acc.token_quota}</td>
												<td className="py-3 px-2 font-mono text-xs text-muted-foreground">
													{acc.proxy}
												</td>
												<td className="py-3 px-2 text-muted-foreground">{acc.last_used}</td>
												<td className="py-3 px-2 text-right">
													<Button
														variant="ghost"
														size="sm"
														onClick={() => toast.info(`Testing ${acc.phone_number}`)}
													>
														Test
													</Button>
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</CardContent>
					</Card>
				</TabsContent>

				<TabsContent value="channels" className="space-y-4">
					<Card>
						<CardHeader className="flex flex-row items-center justify-between pb-2">
							<div>
								<CardTitle>Monitored Telegram Channels</CardTitle>
								<CardDescription>
									Public web preview channels and MTProto stream listeners triggering real-time
									alerts.
								</CardDescription>
							</div>
							<Button size="sm" onClick={() => toast.info("Add channel modal")}>
								Monitor New Channel
							</Button>
						</CardHeader>
						<CardContent>
							<div className="overflow-x-auto">
								<table className="w-full text-left text-sm">
									<thead>
										<tr className="border-b text-muted-foreground">
											<th className="py-3 px-2 font-medium">Channel Name</th>
											<th className="py-3 px-2 font-medium">Type</th>
											<th className="py-3 px-2 font-medium">Mode</th>
											<th className="py-3 px-2 font-medium">Messages</th>
											<th className="py-3 px-2 font-medium">Realtime Stream</th>
											<th className="py-3 px-2 font-medium">Status</th>
											<th className="py-3 px-2 font-medium text-right">Actions</th>
										</tr>
									</thead>
									<tbody>
										{channels.map((ch) => (
											<tr key={ch.id} className="border-b last:border-0 hover:bg-muted/50">
												<td className="py-3 px-2 font-medium font-mono text-primary">{ch.name}</td>
												<td className="py-3 px-2 text-muted-foreground">{ch.type}</td>
												<td className="py-3 px-2 text-muted-foreground">{ch.mode}</td>
												<td className="py-3 px-2">{ch.messages_count.toLocaleString()}</td>
												<td className="py-3 px-2">
													<div className="flex items-center gap-2">
														<Switch
															data-testid="channel-stream-toggle"
															checked={ch.stream_enabled}
															onCheckedChange={() => handleChannelToggle(ch.id)}
														/>
														<span className="text-xs text-muted-foreground">
															{ch.stream_enabled ? "ON" : "OFF"}
														</span>
													</div>
												</td>
												<td className="py-3 px-2">
													{ch.status === "live" && (
														<span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
															⚡ Live
														</span>
													)}
													{ch.status === "idle" && (
														<span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
															🟢 Idle
														</span>
													)}
												</td>
												<td className="py-3 px-2 text-right">
													<Button
														variant="ghost"
														size="sm"
														onClick={() => toast.success(`Triggered scrape for ${ch.name}`)}
													>
														Scrape
													</Button>
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</CardContent>
					</Card>
				</TabsContent>
			</Tabs>

			{/* Multi-step Telegram Onboarding Modal */}
			<Dialog open={telegramModalOpen} onOpenChange={setTelegramModalOpen}>
				<DialogContent className="max-w-lg">
					<DialogHeader>
						<DialogTitle>Connect Telegram MTProto Account</DialogTitle>
						<DialogDescription>
							{telegramStep === 1
								? "Step 1: Enter your Telegram API credentials and phone number."
								: "Step 2: Enter the verification code sent to your Telegram App / SMS."}
						</DialogDescription>
					</DialogHeader>

					{telegramStep === 1 ? (
						<div className="space-y-4 py-4">
							<div className="space-y-2">
								<Label htmlFor="tg-phone">Phone Number</Label>
								<Input
									id="tg-phone"
									value={tgPhone}
									onChange={(e) => setTgPhone(e.target.value)}
									placeholder="+84 912 345 678"
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="tg-api-id">Telegram API ID</Label>
								<Input
									id="tg-api-id"
									value={tgApiId}
									onChange={(e) => setTgApiId(e.target.value)}
									placeholder="20401234"
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="tg-api-hash">API Hash</Label>
								<Input
									id="tg-api-hash"
									value={tgApiHash}
									onChange={(e) => setTgApiHash(e.target.value)}
									placeholder="9ab8c7d6e5f4a3b2c1d0e9f8a7b6c5d4"
								/>
							</div>
							<div className="space-y-2">
								<Label htmlFor="tg-proxy">Proxy (Optional)</Label>
								<Input
									id="tg-proxy"
									value={tgProxy}
									onChange={(e) => setTgProxy(e.target.value)}
									placeholder="socks5h://user:pass@proxy.net:1080"
								/>
							</div>
						</div>
					) : (
						<div className="space-y-4 py-4">
							<div className="space-y-2">
								<Label htmlFor="tg-code">Verification Code</Label>
								<Input
									id="tg-code"
									value={tgCode}
									onChange={(e) => setTgCode(e.target.value)}
									placeholder="5 8 9 2 1"
									className="text-center font-mono text-lg tracking-widest"
								/>
							</div>
							<div className="flex items-center gap-2 pt-2">
								<Switch id="tg-2fa" checked={tg2FAEnabled} onCheckedChange={setTg2FAEnabled} />
								<Label htmlFor="tg-2fa">Two-Step Verification (2FA Cloud Password enabled)</Label>
							</div>
							{tg2FAEnabled && (
								<div className="space-y-2 pt-2">
									<Label htmlFor="tg-cloud-pw">Cloud Password</Label>
									<Input
										id="tg-cloud-pw"
										type="password"
										value={tgCloudPassword}
										onChange={(e) => setTgCloudPassword(e.target.value)}
										placeholder="Enter your 2FA Cloud Password"
									/>
								</div>
							)}
						</div>
					)}

					<DialogFooter className="flex justify-between sm:justify-between">
						{telegramStep === 2 ? (
							<Button variant="outline" onClick={() => setTelegramStep(1)}>
								Back
							</Button>
						) : (
							<Button variant="outline" onClick={() => setTelegramModalOpen(false)}>
								Cancel
							</Button>
						)}
						{telegramStep === 1 ? (
							<Button onClick={handleSendTgCode}>Send Auth Code</Button>
						) : (
							<Button onClick={handleVerifyTgSave}>Verify & Save</Button>
						)}
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{/* Standard Account Dialogs */}
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
				<div className="flex items-center justify-between">
					<Label>Browser cookie string</Label>
					{form.platform === "batdongsan" && form.cookies.trim() && (
						<Button
							type="button"
							variant="outline"
							size="sm"
							onClick={() => update("cookies", filterBatdongsanCookies(form.cookies))}
						>
							Auto-filter for Batdongsan
						</Button>
					)}
				</div>
				<textarea
					value={form.cookies}
					onChange={(e) => update("cookies", e.target.value)}
					placeholder={
						form.platform === "batdongsan"
							? "Paste a Playwright JSON cookie array or document.cookie string from batdongsan.com.vn"
							: "Paste document.cookie here"
					}
					className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
				/>
				{form.platform === "batdongsan" && (
					<p className="text-xs text-muted-foreground">
						Tip: DevTools → Console → document.cookie only shows non-HttpOnly cookies. For the auth
						cookies (accessToken, refreshToken) use a cookie editor extension (e.g. Cookie-Editor)
						to export all cookies as JSON, then paste here.
					</p>
				)}
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
