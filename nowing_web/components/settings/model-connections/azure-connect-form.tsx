import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiKeyField } from "./connect-fields";
import {
	isValidAzureTargetUri,
	type ProviderConnectFormProps,
	parseAzureTargetUri,
} from "./provider-metadata";

/**
 * Azure OpenAI connect form. The user pastes a single Target URI, which we parse
 * into api base, api version, and the deployment name (seeded as the model).
 */
export function AzureConnectForm({ onDraftChange }: ProviderConnectFormProps) {
	const t = useTranslations("settings");
	const [targetUri, setTargetUri] = useState("");
	const [apiKey, setApiKey] = useState("");
	const canSubmit = isValidAzureTargetUri(targetUri) && Boolean(apiKey.trim());

	useEffect(() => {
		const parsed = parseAzureTargetUri(targetUri);
		onDraftChange(
			{
				base_url: parsed?.origin ?? null,
				api_key: apiKey || null,
				extra: parsed?.apiVersion ? { api_version: parsed.apiVersion } : {},
				seedModelId: parsed?.deploymentName || undefined,
			},
			canSubmit
		);
	}, [apiKey, canSubmit, onDraftChange, targetUri]);

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Label>{t("mc_target_uri")}</Label>
				<Input
					value={targetUri}
					onChange={(event) => setTargetUri(event.target.value)}
					placeholder="https://your-resource.cognitiveservices.azure.com/openai/deployments/deployment-name/chat/completions?api-version=2025-01-01-preview"
				/>
				<p className="text-xs text-muted-foreground">{t("mc_target_uri_desc")}</p>
			</div>
			<ApiKeyField value={apiKey} onChange={setApiKey} placeholder={t("mc_azure_key_ph")} />
		</div>
	);
}
