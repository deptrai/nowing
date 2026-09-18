"use client";

import { useTranslations } from "next-intl";
import { KeyRound } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";

export interface BookStackConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const BookStackConfig: FC<BookStackConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const t = useTranslations("assistant");
	const [baseUrl, setBaseUrl] = useState<string>(
		(connector.config?.BOOKSTACK_BASE_URL as string) || ""
	);
	const [tokenId, setTokenId] = useState<string>(
		(connector.config?.BOOKSTACK_TOKEN_ID as string) || ""
	);
	const [tokenSecret, setTokenSecret] = useState<string>(
		(connector.config?.BOOKSTACK_TOKEN_SECRET as string) || ""
	);
	const [name, setName] = useState<string>(connector.name || "");

	const handleBaseUrlChange = (value: string) => {
		setBaseUrl(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_BASE_URL: value,
			});
		}
	};

	const handleTokenIdChange = (value: string) => {
		setTokenId(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_TOKEN_ID: value,
			});
		}
	};

	const handleTokenSecretChange = (value: string) => {
		setTokenSecret(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				BOOKSTACK_TOKEN_SECRET: value,
			});
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">{t("connector_name")}</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder={t("bookstack_name_placeholder")}
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
						<Label className="text-xs sm:text-sm">{t("bookstack_base_url")}</Label>
						<Input
							type="url"
							value={baseUrl}
							onChange={(e) => handleBaseUrlChange(e.target.value)}
							placeholder="https://your-bookstack-instance.com"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("bookstack_base_url_short")}
						</p>
					</div>

					<div className="space-y-2">
						<Label className="text-xs sm:text-sm">{t("token_id")}</Label>
						<Input
							value={tokenId}
							onChange={(e) => handleTokenIdChange(e.target.value)}
							placeholder={t("bookstack_token_placeholder")}
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("bookstack_token_id_desc")}
						</p>
					</div>

					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" aria-hidden="true" />
							{t("token_secret")}
						</Label>
						<Input
							type="password"
							value={tokenSecret}
							onChange={(e) => handleTokenSecretChange(e.target.value)}
							placeholder={t("bookstack_secret_placeholder")}
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("bookstack_update_secret")}
						</p>
					</div>
				</div>
			</div>
		</div>
	);
};
