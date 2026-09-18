"use client";

import { AlertCircle, CheckCircle2, Hash, Info, Lock, RefreshCw } from "lucide-react";
import { type FC, useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { connectorsApiService, type SlackChannel } from "@/lib/apis/connectors-api.service";
import { cn } from "@/lib/utils";
import type { ConnectorConfigProps } from "../index";
import { useTranslations } from "next-intl";

export interface SlackConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const SlackConfig: FC<SlackConfigProps> = ({ connector }) => {
	const t = useTranslations("assistant");
	const [channels, setChannels] = useState<SlackChannel[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [lastFetched, setLastFetched] = useState<Date | null>(null);

	const fetchChannels = useCallback(async () => {
		if (!connector?.id) return;

		setIsLoading(true);
		setError(null);

		try {
			const data = await connectorsApiService.getSlackChannels(connector.id);
			setChannels(data);
			setLastFetched(new Date());
		} catch (err) {
			console.error("Failed to fetch Slack channels:", err);
			setError(err instanceof Error ? err.message : t("failed_fetch_channels"));
		} finally {
			setIsLoading(false);
		}
	}, [connector?.id]);

	// Fetch channels on mount
	useEffect(() => {
		fetchChannels();
	}, [fetchChannels]);

	// Auto-refresh when user returns to tab
	useEffect(() => {
		const handleVisibilityChange = () => {
			if (document.visibilityState === "visible" && connector?.id) {
				fetchChannels();
			}
		};

		document.addEventListener("visibilitychange", handleVisibilityChange);
		return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
	}, [connector?.id, fetchChannels]);

	// Separate channels by bot membership
	const channelsWithBot = channels.filter((ch) => ch.is_member);
	const channelsWithoutBot = channels.filter((ch) => !ch.is_member);

	// Format last fetched time
	const formatLastFetched = () => {
		if (!lastFetched) return null;
		const now = new Date();
		const diffMs = now.getTime() - lastFetched.getTime();
		const diffSecs = Math.floor(diffMs / 1000);
		const diffMins = Math.floor(diffSecs / 60);

		if (diffSecs < 60) return t("just_now");
		if (diffMins === 1) return t("minute_ago");
		if (diffMins < 60) return t("minutes_ago", { count: diffMins });
		return lastFetched.toLocaleTimeString();
	};

	return (
		<div className="space-y-6">
			{/* Info box */}
			<Alert>
				<Info />
				<AlertTitle>{t("add_bot_to_channels")}</AlertTitle>
				<AlertDescription>
					<p>
						{t.rich("add_bot_desc", {
							command: () => (
								<code className="rounded bg-popover px-1 py-0.5 text-[9px] text-popover-foreground">
									/invite @Nowing
								</code>
							),
						})}
					</p>
				</AlertDescription>
			</Alert>

			{/* Channels Section */}
			<div className="space-y-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-3">
						<h3 className="text-sm font-semibold">{t("channel_access")}</h3>
					</div>
					<div className="flex items-center gap-2">
						{lastFetched && (
							<span className="text-[10px] text-muted-foreground">{formatLastFetched()}</span>
						)}
						<Button
							variant="secondary"
							size="sm"
							onClick={fetchChannels}
							disabled={isLoading}
							className="h-7 px-2.5 text-[11px] bg-slate-400/10 dark:bg-white/10 hover:bg-accent hover:text-accent-foreground border-slate-400/20 dark:border-white/20"
						>
							<RefreshCw className={cn("mr-1.5 size-3", isLoading && "animate-spin")} />
							{t("refresh")}
						</Button>
					</div>
				</div>

				{error && (
					<div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-xs text-destructive">
						{error}
					</div>
				)}

				{isLoading && channels.length === 0 ? (
					<div className="flex items-center justify-center py-8">
						<Spinner size="sm" />
						<span className="ml-2 text-sm text-muted-foreground">{t("loading_channels")}</span>
					</div>
				) : channels.length === 0 && !error ? (
					<div className="text-center py-8 text-sm text-muted-foreground">
						{t("no_channels_slack")}
					</div>
				) : (
					<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 overflow-hidden">
						{/* Channels with bot access */}
						{channelsWithBot.length > 0 && (
							<div className={cn("p-3", channelsWithoutBot.length > 0 && "border-b border-border")}>
								<div className="flex items-center gap-2 mb-2">
									<CheckCircle2 className="size-3.5 text-emerald-500" aria-hidden="true" />
									<span className="text-[11px] font-medium">{t("ready_to_index")}</span>
									<span className="text-[10px] text-muted-foreground">
										{t("channels_count", { count: channelsWithBot.length })}
									</span>
								</div>
								<div className="flex flex-wrap gap-1.5">
									{channelsWithBot.map((channel) => (
										<ChannelPill key={channel.id} channel={channel} />
									))}
								</div>
							</div>
						)}

						{/* Channels without bot access */}
						{channelsWithoutBot.length > 0 && (
							<div className="p-3">
								<div className="flex items-center gap-2 mb-2">
									<AlertCircle className="size-3.5 text-amber-500" aria-hidden="true" />
									<span className="text-[11px] font-medium">{t("add_bot_to_index")}</span>
									<span className="text-[10px] text-muted-foreground">
										{t("channels_count", { count: channelsWithoutBot.length })}
									</span>
								</div>
								<div className="flex flex-wrap gap-1.5">
									{channelsWithoutBot.map((channel) => (
										<ChannelPill key={channel.id} channel={channel} />
									))}
								</div>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

interface ChannelPillProps {
	channel: SlackChannel;
}

const ChannelPill: FC<ChannelPillProps> = ({ channel }) => {
	return (
		<div className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-slate-400/10 dark:bg-white/10 hover:bg-accent hover:text-accent-foreground transition-colors">
			{channel.is_private ? (
				<Lock className="size-2.5 text-muted-foreground" aria-hidden="true" />
			) : (
				<Hash className="size-2.5 text-muted-foreground" aria-hidden="true" />
			)}
			<span>{channel.name}</span>
		</div>
	);
};
