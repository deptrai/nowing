"use client";

import { AlertTriangle, RefreshCw, ShieldAlert } from "lucide-react";
import { useParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { GetWorkspaceResponse, Workspace } from "@/contracts/types/workspace.types";
import { userApiService } from "@/lib/apis/user-api.service";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";

type GatewayConnection = {
	id: number;
	account_id?: number | null;
	route_type?: "account" | "binding";
	platform: string;
	mode?: string;
	state: string;
	workspace_id: number;
	display_name?: string | null;
	external_username?: string | null;
	workspace_name?: string | null;
	health_status: string;
	suspended_reason?: string | null;
};

type GatewayConfig = {
	enabled: boolean;
	telegram_enabled: boolean;
	whatsapp_intake_mode: "disabled" | "cloud" | "baileys";
	slack_enabled: boolean;
	discord_enabled: boolean;
};

type GatewayConfigState = GatewayConfig | null;

const DISABLED_GATEWAY_CONFIG: GatewayConfig = {
	enabled: false,
	telegram_enabled: false,
	whatsapp_intake_mode: "disabled",
	slack_enabled: false,
	discord_enabled: false,
};

type Pairing = {
	binding_id: number;
	code: string;
	deep_link: string;
	expires_at: string;
};

type PairingPlatform = "telegram" | "whatsapp";
type GatewayPlatform = PairingPlatform | "slack" | "discord";

type BaileysHealth = {
	status: string;
	hasQr: boolean;
	qr?: string | null;
	queueDepth?: number;
	user?: unknown;
};

export function MessagingChannelsContent() {
	const params = useParams<{ workspace_id: string }>();
	const workspaceId = Number(params.workspace_id);
	const [gatewayConfig, setGatewayConfig] = useState<GatewayConfigState>(null);
	const [connections, setConnections] = useState<GatewayConnection[]>([]);
	const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
	const [workspace, setWorkspace] = useState<GetWorkspaceResponse | null>(null);
	const [pairing, setPairing] = useState<Pairing | null>(null);
	const [pairingPlatform, setPairingPlatform] = useState<PairingPlatform | null>(null);
	const [baileysHealth, setBaileysHealth] = useState<BaileysHealth | null>(null);
	const [refreshingPlatform, setRefreshingPlatform] = useState<GatewayPlatform | null>(null);
	const [telegramNotificationsEnabled, setTelegramNotificationsEnabled] = useState(false);
	const [isLoadingUserProfile, setIsLoadingUserProfile] = useState(true);
	const [isSavingNotifications, setIsSavingNotifications] = useState(false);
	// Story 24.6: two-way auto-reply agent settings (local state until API exists)
	const [autoReplyEnabled, setAutoReplyEnabled] = useState(false);
	const [autoReplyCollections, setAutoReplyCollections] = useState<string[]>([]);
	const [autoReplyFallback, setAutoReplyFallback] = useState("");
	const [autoReplyRecipientChatId, setAutoReplyRecipientChatId] = useState("");
	const [isSavingAutoReply, setIsSavingAutoReply] = useState(false);
	const isGatewayConfigLoading = gatewayConfig === null;
	const telegramGatewayEnabled = gatewayConfig?.telegram_enabled ?? false;
	const whatsappMode = gatewayConfig?.whatsapp_intake_mode ?? "disabled";
	const slackGatewayEnabled = gatewayConfig?.slack_enabled ?? false;
	const discordGatewayEnabled = gatewayConfig?.discord_enabled ?? false;
	const gatewayDisabled = gatewayConfig?.enabled === false;

	const fetchConnections = useCallback(async (platform?: GatewayPlatform) => {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/connections", platform ? { platform } : undefined)
		);
		if (!res.ok) return [];
		const data = await res.json();
		return Array.isArray(data) ? (data as GatewayConnection[]) : [];
	}, []);

	const fetchGatewayConfig = useCallback(async (): Promise<GatewayConfig> => {
		const res = await authenticatedFetch(buildBackendUrl("/api/v1/gateway/config"));
		if (!res.ok) return DISABLED_GATEWAY_CONFIG;
		const data = (await res.json()) as Partial<GatewayConfig>;
		return {
			...DISABLED_GATEWAY_CONFIG,
			...data,
			enabled: data.enabled ?? true,
		};
	}, []);

	const refresh = useCallback(async () => {
		const [nextConnections, spaces, nextWorkspace, nextGatewayConfig] = await Promise.all([
			fetchConnections(),
			workspacesApiService.getWorkspaces(),
			workspacesApiService.getWorkspace({ id: workspaceId }).catch(() => null),
			fetchGatewayConfig(),
		]);
		setConnections(nextConnections);
		setWorkspaces(spaces);
		setWorkspace(nextWorkspace);
		setGatewayConfig(nextGatewayConfig);
	}, [fetchConnections, fetchGatewayConfig, workspaceId]);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	// Sync local auto-reply controls from workspace settings.
	useEffect(() => {
		if (workspace) {
			setAutoReplyEnabled(workspace.auto_reply_enabled ?? false);
			setAutoReplyCollections(
				Array.isArray(workspace.auto_reply_collections)
					? workspace.auto_reply_collections.map(String)
					: []
			);
			setAutoReplyFallback(workspace.auto_reply_fallback ?? "");
			setAutoReplyRecipientChatId(workspace.auto_reply_recipient_chat_id ?? "");
		}
	}, [workspace]);

	const refreshPlatform = useCallback(
		async (platform: GatewayPlatform) => {
			setRefreshingPlatform(platform);
			try {
				const nextConnections = await fetchConnections(platform);
				setConnections((current) => [
					...current.filter((connection) => connection.platform !== platform),
					...nextConnections,
				]);
			} finally {
				setRefreshingPlatform(null);
			}
		},
		[fetchConnections]
	);

	const refreshBaileysHealth = useCallback(async () => {
		if (whatsappMode !== "baileys") return;
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/whatsapp/baileys/health")
		);
		if (!res.ok) return;
		const data = (await res.json()) as BaileysHealth;
		setBaileysHealth(data);
	}, [whatsappMode]);

	useEffect(() => {
		void refreshBaileysHealth();
	}, [refreshBaileysHealth]);

	useEffect(() => {
		userApiService
			.getMe()
			.then((user) => {
				const prefs = user.notification_preferences as Record<
					string,
					Record<string, unknown> | unknown
				> | null;
				const automationPrefs = prefs?.automation_run_complete as
					| Record<string, unknown>
					| undefined;
				setTelegramNotificationsEnabled(automationPrefs?.telegram === true);
			})
			.catch(() => {
				setTelegramNotificationsEnabled(false);
			})
			.finally(() => {
				setIsLoadingUserProfile(false);
			});
	}, []);

	async function toggleTelegramNotifications(enabled: boolean) {
		setTelegramNotificationsEnabled(enabled);
		setIsSavingNotifications(true);
		try {
			const res = await authenticatedFetch(buildBackendUrl("/users/me/notification-preferences"), {
				method: "PATCH",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					notification_preferences: {
						automation_run_complete: { telegram: enabled },
					},
				}),
			});
			if (!res.ok) {
				setTelegramNotificationsEnabled(!enabled);
				toast.error("Failed to update Telegram notification preference");
				return;
			}
			toast.success(
				enabled ? "Telegram run notifications enabled" : "Telegram run notifications disabled"
			);
		} catch {
			setTelegramNotificationsEnabled(!enabled);
			toast.error("Failed to update Telegram notification preference");
		} finally {
			setIsSavingNotifications(false);
		}
	}

	async function saveAutoReply(partial: Partial<Workspace>) {
		setIsSavingAutoReply(true);
		try {
			const updated = await workspacesApiService.updateWorkspace({
				id: workspaceId,
				data: partial,
			});
			setWorkspace(updated);
			toast.success("Auto-reply settings saved");
			return updated;
		} catch {
			toast.error("Failed to update auto-reply settings");
			throw new Error("Failed to update auto-reply settings");
		} finally {
			setIsSavingAutoReply(false);
		}
	}

	async function toggleAutoReply(enabled: boolean) {
		setAutoReplyEnabled(enabled);
		try {
			await saveAutoReply({ auto_reply_enabled: enabled });
		} catch {
			setAutoReplyEnabled(!enabled);
		}
	}

	async function startPairing(platform: PairingPlatform) {
		const res = await authenticatedFetch(buildBackendUrl("/api/v1/gateway/bindings/start"), {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ platform, workspace_id: workspaceId }),
		});
		setPairing(await res.json());
		setPairingPlatform(platform);
		await refreshPlatform(platform);
	}

	async function installSlackGateway() {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/slack/install", { workspace_id: workspaceId })
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	async function installDiscordGateway() {
		const res = await authenticatedFetch(
			buildBackendUrl("/api/v1/gateway/discord/install", { workspace_id: workspaceId })
		);
		if (!res.ok) return;
		const data = (await res.json()) as { auth_url?: string };
		if (data.auth_url) {
			window.location.href = data.auth_url;
		}
	}

	async function refreshBaileys() {
		await refreshBaileysHealth();
		await refreshPlatform("whatsapp");
	}

	const connectionKey = (connection: GatewayConnection) =>
		connection.route_type === "account" && connection.account_id
			? `account:${connection.account_id}`
			: `binding:${connection.id}`;

	async function revoke(connection: GatewayConnection) {
		const url =
			connection.route_type === "account" && connection.account_id
				? buildBackendUrl(`/api/v1/gateway/accounts/${connection.account_id}`)
				: buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}`);
		await authenticatedFetch(url, {
			method: "DELETE",
		});
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	async function updateConnectionWorkspace(connection: GatewayConnection, nextWorkspaceId: string) {
		const previousConnections = connections;
		const parsedWorkspaceId = Number(nextWorkspaceId);
		const targetKey = connectionKey(connection);
		setConnections((current) =>
			current.map((connection) =>
				connectionKey(connection) === targetKey
					? { ...connection, workspace_id: parsedWorkspaceId }
					: connection
			)
		);
		const url =
			connection.route_type === "account" && connection.account_id
				? buildBackendUrl(`/api/v1/gateway/accounts/${connection.account_id}/workspace`)
				: buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}/workspace`);
		const res = await authenticatedFetch(url, {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ workspace_id: parsedWorkspaceId }),
		});
		if (!res.ok) {
			setConnections(previousConnections);
			toast.error("Failed to update messaging route");
			return;
		}
		toast.success("Messaging route updated");
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	async function resume(connection: GatewayConnection) {
		await authenticatedFetch(buildBackendUrl(`/api/v1/gateway/bindings/${connection.id}/resume`), {
			method: "POST",
		});
		await refreshPlatform(connection.platform as GatewayPlatform);
	}

	const isConnectionInActiveMode = (connection: GatewayConnection) => {
		if (connection.platform !== "whatsapp") return true;
		if (whatsappMode === "baileys") return connection.mode === "self_host_byo";
		if (whatsappMode === "cloud") return connection.mode !== "self_host_byo";
		return false;
	};
	const baileysQr = baileysHealth?.qr || null;
	const hasTelegramConnection = connections.some(
		(connection) => connection.platform === "telegram" && connection.state === "bound"
	);
	const hasWhatsAppConnection = connections.some(
		(connection) => connection.platform === "whatsapp" && isConnectionInActiveMode(connection)
	);
	const hasEnabledGateway =
		telegramGatewayEnabled ||
		whatsappMode !== "disabled" ||
		slackGatewayEnabled ||
		discordGatewayEnabled;
	const isRefreshing = (platform: GatewayPlatform) => refreshingPlatform === platform;
	const refreshButtonClassName = "gap-2";
	const refreshIconClassName = (platform: GatewayPlatform) =>
		cn("mr-2 h-4 w-4", isRefreshing(platform) && "animate-spin");
	const platformLabel = (platform: string) => {
		switch (platform) {
			case "discord":
				return "Discord";
			case "slack":
				return "Slack";
			case "telegram":
				return "Telegram";
			case "whatsapp":
				return "WhatsApp";
			default:
				return platform;
		}
	};
	const connectionTitle = (connection: GatewayConnection) =>
		connection.platform === "whatsapp" && connection.mode === "self_host_byo"
			? "WhatsApp Bridge"
			: connection.workspace_name ||
				connection.display_name ||
				connection.external_username ||
				`${platformLabel(connection.platform)} connection`;
	const renderConnectionRows = (platform: GatewayConnection["platform"], emptyText: string) => {
		const platformConnections = connections.filter(
			(connection) => connection.platform === platform && isConnectionInActiveMode(connection)
		);

		if (platformConnections.length === 0) {
			return (
				<div className="flex min-h-24 items-center justify-center text-center">
					<p className="text-xs text-muted-foreground">{emptyText}</p>
				</div>
			);
		}

		return (
			<div className="space-y-2">
				<p className="text-xs font-medium text-muted-foreground">Connected accounts</p>
				{platformConnections.map((connection, index) => (
					<div key={connectionKey(connection)} className="space-y-2">
						{index > 0 ? <Separator className="bg-accent" /> : null}
						<div className="space-y-2">
							<div className="min-w-0">
								<p className="truncate text-xs font-medium">{connectionTitle(connection)}</p>
								{connection.suspended_reason ? (
									<p className="mt-1 flex items-center gap-1 text-xs text-destructive">
										<ShieldAlert className="h-3 w-3" aria-hidden="true" />
										{connection.suspended_reason}
									</p>
								) : null}
							</div>
							<div className="flex flex-wrap items-center gap-2">
								<Select
									value={String(connection.workspace_id)}
									onValueChange={(value) => updateConnectionWorkspace(connection, value)}
									disabled={workspaces.length === 0}
								>
									<SelectTrigger className="h-8 min-w-[180px] flex-1 text-xs">
										<SelectValue placeholder="Select workspace" />
									</SelectTrigger>
									<SelectContent>
										{workspaces.map((space) => (
											<SelectItem key={space.id} value={String(space.id)}>
												{space.name}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
								{connection.state === "suspended" ? (
									<Button
										size="sm"
										variant="outline"
										className="h-8"
										onClick={() => resume(connection)}
									>
										Resume
									</Button>
								) : null}
								<Button
									size="sm"
									variant="destructive"
									className="text-xs sm:text-sm flex-1 sm:flex-initial h-12 sm:h-auto py-3 sm:py-2"
									onClick={() => revoke(connection)}
								>
									Disconnect
								</Button>
							</div>
						</div>
					</div>
				))}
			</div>
		);
	};
	const renderPairingPanel = (platform: PairingPlatform) => {
		if (!pairing || pairingPlatform !== platform) return null;

		return (
			<div className="rounded-lg border border-accent bg-accent/20 p-3">
				<p className="text-xs font-medium">Pairing code</p>
				<p className="mt-2 font-mono text-lg">{pairing.code}</p>
				<a className="mt-2 block text-sm text-primary underline" href={pairing.deep_link}>
					Open {platform === "whatsapp" ? "WhatsApp" : "Telegram"} pairing link
				</a>
				<p className="mt-2 text-xs text-muted-foreground">
					Expires at {new Date(pairing.expires_at).toLocaleString()}. Nowing stores this channel's
					messages for agent memory and operational debugging.
				</p>
			</div>
		);
	};
	const renderGatewaySkeletons = () => (
		<>
			{[0, 1].map((index) => (
				<Card key={index} className="h-full overflow-hidden border-accent bg-accent/20">
					<CardHeader className="space-y-3 p-4">
						<Skeleton className="h-4 w-24 bg-accent" aria-hidden="true" />
						<Skeleton className="h-3 w-3/4 bg-accent" aria-hidden="true" />
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<Skeleton className="h-8 w-40 bg-accent" aria-hidden="true" />
						<Separator className="bg-accent" />
						<Skeleton className="h-10 w-full bg-accent" />
					</CardContent>
				</Card>
			))}
		</>
	);

	return (
		<div className="grid items-stretch gap-3 sm:grid-cols-2">
			{isGatewayConfigLoading ? renderGatewaySkeletons() : null}

			{!isGatewayConfigLoading && gatewayDisabled ? (
				<Alert className="col-span-full" variant="warning">
					<AlertTriangle aria-hidden />
					<AlertTitle>Messaging Channels coming soon</AlertTitle>
					<AlertDescription>
						<p>
							Soon you'll be able to connect WhatsApp, Telegram, Slack, and Discord to your Nowing
							agent so you can ask questions, route messages to workspaces, and get answers from
							your knowledge base without leaving your chat app.
						</p>
					</AlertDescription>
				</Alert>
			) : null}

			{!isGatewayConfigLoading && !gatewayDisabled && !hasEnabledGateway ? (
				<Card className="col-span-full border-accent bg-accent/20">
					<CardHeader className="space-y-1.5 p-4">
						<CardTitle className="text-sm">No messaging gateways enabled</CardTitle>
					</CardHeader>
				</Card>
			) : null}

			{!gatewayDisabled && telegramGatewayEnabled ? (
				<Card className="order-1 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Telegram</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">Connect Telegram to chat with Nowing.</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							{hasTelegramConnection ? null : (
								<Button size="sm" onClick={() => startPairing("telegram")}>
									Pair Telegram Chat
								</Button>
							)}
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("telegram")}
								disabled={isRefreshing("telegram")}
							>
								<RefreshCw className={refreshIconClassName("telegram")} />
								Refresh
							</Button>
						</div>

						{hasTelegramConnection ? null : renderPairingPanel("telegram")}
						{hasTelegramConnection ? (
							<div className="flex items-center justify-between gap-3 rounded-md border border-accent/50 bg-accent/10 p-3">
								<div className="space-y-0.5">
									<p className="text-sm font-medium">Automation run notifications</p>
									<p className="text-xs text-muted-foreground">
										Notify me on Telegram when an automation run completes
									</p>
								</div>
								<Switch
									checked={telegramNotificationsEnabled}
									onCheckedChange={toggleTelegramNotifications}
									disabled={isLoadingUserProfile || isSavingNotifications}
									aria-label="Notify me on Telegram when an automation run completes"
								/>
							</div>
						) : null}
						<Separator className="bg-accent" />
						{renderConnectionRows("telegram", "No Telegram chats connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && slackGatewayEnabled ? (
				<Card className="order-4 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Slack</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							Enable the Nowing Slack bot so teammates can mention it in Slack.
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							<Button size="sm" onClick={installSlackGateway}>
								Add Slack Workspace
							</Button>
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("slack")}
								disabled={isRefreshing("slack")}
							>
								<RefreshCw className={refreshIconClassName("slack")} />
								Refresh
							</Button>
						</div>
						<Separator className="bg-accent" />
						{renderConnectionRows("slack", "No Slack workspaces connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && discordGatewayEnabled ? (
				<Card className="order-3 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">Discord</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							Enable the Nowing Discord bot so teammates can mention it in Discord.
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						<div className="flex flex-wrap gap-2">
							<Button size="sm" onClick={installDiscordGateway}>
								Add Discord Server
							</Button>
							<Button
								size="sm"
								variant="secondary"
								className={refreshButtonClassName}
								onClick={() => refreshPlatform("discord")}
								disabled={isRefreshing("discord")}
							>
								<RefreshCw className={refreshIconClassName("discord")} />
								Refresh
							</Button>
						</div>
						<Separator className="bg-accent" />
						{renderConnectionRows("discord", "No Discord servers connected yet.")}
					</CardContent>
				</Card>
			) : null}

			{!gatewayDisabled && whatsappMode !== "disabled" ? (
				<Card className="order-2 group relative h-full overflow-hidden border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
					<CardHeader className="space-y-1.5 p-4 pb-2">
						<div className="flex items-center justify-between gap-3">
							<CardTitle className="flex items-center gap-2 text-sm">WhatsApp</CardTitle>
						</div>
						<p className="text-xs text-muted-foreground">
							{whatsappMode === "baileys"
								? 'Use "Message Yourself". Other chats are ignored.'
								: "Connect WhatsApp to chat with Nowing."}
						</p>
					</CardHeader>
					<CardContent className="space-y-3 p-4 pt-0">
						{whatsappMode === "cloud" ? (
							<div className="space-y-3">
								<div className="flex flex-wrap gap-2">
									{hasWhatsAppConnection ? null : (
										<Button size="sm" onClick={() => startPairing("whatsapp")}>
											Pair WhatsApp
										</Button>
									)}
									<Button
										size="sm"
										variant="secondary"
										className={refreshButtonClassName}
										onClick={() => refreshPlatform("whatsapp")}
										disabled={isRefreshing("whatsapp")}
									>
										<RefreshCw className={refreshIconClassName("whatsapp")} />
										Refresh
									</Button>
								</div>
								{hasWhatsAppConnection ? null : renderPairingPanel("whatsapp")}
							</div>
						) : null}
						{whatsappMode === "baileys" ? (
							<div className="space-y-3">
								<Button
									size="sm"
									variant="secondary"
									className={refreshButtonClassName}
									onClick={refreshBaileys}
									disabled={isRefreshing("whatsapp")}
								>
									<RefreshCw className={refreshIconClassName("whatsapp")} />
									Refresh
								</Button>
								{baileysQr ? (
									<div className="rounded-lg border border-accent bg-accent/20 p-3">
										<p className="text-sm font-medium">WhatsApp QR pairing</p>
										<p className="mt-1 text-xs text-muted-foreground">
											Scan this QR from WhatsApp &gt; Linked Devices &gt; Link a Device.
										</p>
										<div className="mt-3 inline-block rounded-md bg-white p-3">
											<QRCodeSVG value={baileysQr} size={192} />
										</div>
									</div>
								) : null}
								{baileysHealth ? (
									<p className="text-xs text-muted-foreground">
										Bridge status: {baileysHealth.status}
										{typeof baileysHealth.queueDepth === "number"
											? `, queue: ${baileysHealth.queueDepth}`
											: ""}
									</p>
								) : null}
							</div>
						) : null}
						<Separator className="bg-accent" />
						{renderConnectionRows("whatsapp", "No WhatsApp chats connected yet.")}
					</CardContent>
				</Card>
			) : null}

			<Card className="order-3 group relative h-full overflow-hidden border-primary/30 bg-primary/5 transition-all duration-200 hover:shadow-md col-span-full">
				<CardHeader className="space-y-1.5 p-4 pb-2">
					<div className="flex items-center justify-between gap-3">
						<CardTitle className="flex items-center gap-2 text-sm">
							<span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
							AI Tự Động Trả Lời Tin Nhắn 24/7 (Two-Way Auto-Reply Agent)
						</CardTitle>
						<Switch
							data-testid="auto-reply-toggle"
							checked={autoReplyEnabled}
							onCheckedChange={toggleAutoReply}
							disabled={isSavingAutoReply}
						/>
					</div>
					<p className="text-xs text-muted-foreground">
						Tự động trả lời thắc mắc của khách hàng trên Zalo OA / Telegram dựa trên tài liệu
						Knowledge Base của workspace. Phát hiện ý định mua hàng (Buying Signals) và bắn alert
						Telegram cho nhân viên nhận tư vấn (tự động khóa AI 24h khi con người can thiệp).
					</p>
				</CardHeader>
				<CardContent className="space-y-3 p-4 pt-2">
					<div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
						<span className="rounded bg-background/80 px-2 py-0.5 border">
							RAG Cosine &ge; 0.75 Grounding
						</span>
						<span className="rounded bg-background/80 px-2 py-0.5 border">
							Anti-Hallucination Safe Fallback
						</span>
						<span className="rounded bg-background/80 px-2 py-0.5 border">3s Debounce Buffer</span>
						<span className="rounded bg-background/80 px-2 py-0.5 border">
							24h Human Takeover Pause
						</span>
					</div>
					<div className="grid gap-3">
						<div className="space-y-1">
							<label htmlFor="autoReplyCollections" className="text-xs font-medium">
								KB Collections
							</label>
							<Select
								disabled={isSavingAutoReply}
								value={autoReplyCollections.length ? autoReplyCollections.join(",") : "none"}
								onValueChange={(v) => {
									const next = v && v !== "none" ? v.split(",") : [];
									setAutoReplyCollections(next);
									void saveAutoReply({ auto_reply_collections: next.map(Number).filter(Boolean) });
								}}
							>
								<SelectTrigger id="autoReplyCollections" className="h-8 text-xs">
									<SelectValue placeholder="Chọn KB collections (coming soon)" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="none">Chưa có collection nào</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div className="space-y-1">
							<label htmlFor="autoReplyFallback" className="text-xs font-medium">
								Fallback Message
							</label>
							<Textarea
								id="autoReplyFallback"
								data-testid="auto-reply-fallback"
								disabled={isSavingAutoReply}
								value={autoReplyFallback}
								onChange={(e) => setAutoReplyFallback(e.target.value)}
								onBlur={() => void saveAutoReply({ auto_reply_fallback: autoReplyFallback })}
								placeholder="Tin nhắn dự phòng khi không có tài liệu liên quan..."
								className="min-h-[60px] text-xs"
							/>
						</div>
						<div className="space-y-1">
							<label htmlFor="autoReplyRecipientChatId" className="text-xs font-medium">
								Hot-Lead Recipient Chat ID
							</label>
							<Input
								id="autoReplyRecipientChatId"
								data-testid="auto-reply-recipient"
								disabled={isSavingAutoReply}
								value={autoReplyRecipientChatId}
								onChange={(e) => setAutoReplyRecipientChatId(e.target.value)}
								onBlur={() =>
									void saveAutoReply({
										auto_reply_recipient_chat_id: autoReplyRecipientChatId,
									})
								}
								placeholder="e.g. @sales_channel hoặc Telegram chat id"
								className="h-8 text-xs"
							/>
						</div>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
