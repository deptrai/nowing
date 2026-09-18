"use client";

import { useTranslations } from "next-intl";
import { Info, KeyRound } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface ConfluenceConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const ConfluenceConfig: FC<ConfluenceConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const t = useTranslations("assistant");// Check if this is an OAuth connector (has access_token or _token_encrypted flag)
	const isOAuth = !!(connector.config?.access_token || connector.config?._token_encrypted);

	const [baseUrl, setBaseUrl] = useState<string>(
		(connector.config?.CONFLUENCE_BASE_URL as string) || ""
	);
	const [email, setEmail] = useState<string>((connector.config?.CONFLUENCE_EMAIL as string) || "");
	const [apiToken, setApiToken] = useState<string>(
		(connector.config?.CONFLUENCE_API_TOKEN as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");

	const handleBaseUrlChange = (value: string) => {
		setBaseUrl(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				CONFLUENCE_BASE_URL: value,
			});
		}
	};

	const handleEmailChange = (value: string) => {
		setEmail(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				CONFLUENCE_EMAIL: value,
			});
		}
	};

	const handleApiTokenChange = (value: string) => {
		setApiToken(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				CONFLUENCE_API_TOKEN: value,
			});
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	// For OAuth connectors, show simple info message
	if (isOAuth) {
		const siteUrl =
			(connector.config?.base_url as string) || (connector.config?.site_url as string) || "Unknown";
		return (
			<div className="space-y-6">
				{/* OAuth Info */}
				<Alert>
					<Info />
					<AlertTitle>{t("connected_oauth")}</AlertTitle>
					<AlertDescription>
						<p>{t("confluence_oauth_desc")}</p>
						<p>
							<code className="bg-muted px-1 py-0.5 rounded text-inherit">{siteUrl}</code>
						</p>
						<p>{t("oauth_reconnect")}</p>
					</AlertDescription>
				</Alert>
			</div>
		);
	}

	// For legacy API token connectors, show the form
	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">{t("connector_name")}</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder={t("confluence_name_placeholder")}
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						{t("connector_name_desc")}
					</p>
				</div>
			</div>

			{/* Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">{t("configuration")}</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">{t("confluence_base_url")}</Label>
						<Input
							type="url"
							value={baseUrl}
							onChange={(e) => handleBaseUrlChange(e.target.value)}
							placeholder="https://your-domain.atlassian.net"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("confluence_base_url_desc")}
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">{t("confluence_email")}</Label>
						<Input
							type="email"
							value={email}
							onChange={(e) => handleEmailChange(e.target.value)}
							placeholder={t("confluence_email_placeholder")}
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("confluence_email_desc")}
						</p>
					</div>

					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" aria-hidden="true" />
							{t("confluence_api_token")}
						</Label>
						<Input
							type="password"
							value={apiToken}
							onChange={(e) => handleApiTokenChange(e.target.value)}
							placeholder={t("confluence_api_token_placeholder")}
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("confluence_update_token_2")}
						</p>
					</div>
				</div>
			</div>
		</div>
	);
};
