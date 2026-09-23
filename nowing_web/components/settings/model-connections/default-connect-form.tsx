import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ApiBaseUrlField, ApiKeyField } from "./connect-fields";
import type { ProviderConnectFormProps } from "./provider-metadata";

const OPTIONAL_API_KEY_PROVIDERS = new Set(["ollama_chat", "lm_studio", "openai_compatible"]);

function baseUrlHint(t: (k: string) => string, provider: string) {
	if (provider === "ollama_chat" || provider === "lm_studio") {
		return t("mc_hint_local");
	}
	if (provider === "openai_compatible") {
		return t("mc_hint_v1");
	}
	if (provider === "openai_compatible_raw") {
		return t("mc_hint_exact");
	}
	if (
		provider === "openai" ||
		provider === "anthropic" ||
		provider === "openrouter" ||
		provider === "requesty"
	) {
		return t("mc_hint_proxy");
	}
	return undefined;
}

/**
 * Connect form for OpenAI-compatible / native key providers (OpenAI, Anthropic,
 * OpenRouter, OpenAI-Compatible, LM Studio, Ollama, …). The base URL is
 * prefilled from the provider default.
 */
export function DefaultConnectForm({
	provider,
	defaultBaseUrl,
	baseUrlRequired,
	onDraftChange,
}: ProviderConnectFormProps) {
	const t = useTranslations("settings");
	const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
	const [apiKey, setApiKey] = useState("");
	const isApiKeyOptional = OPTIONAL_API_KEY_PROVIDERS.has(provider);
	const hint = baseUrlHint(t, provider);
	const apiKeyValue = apiKey.trim();
	const canSubmit =
		!(baseUrlRequired && !baseUrl.trim()) && (isApiKeyOptional || Boolean(apiKeyValue));

	useEffect(() => {
		onDraftChange(
			{ base_url: baseUrl || null, api_key: apiKeyValue || null, extra: {} },
			canSubmit
		);
	}, [apiKeyValue, baseUrl, canSubmit, onDraftChange]);

	return (
		<div className="flex flex-col gap-4">
			<ApiBaseUrlField
				value={baseUrl}
				onChange={setBaseUrl}
				placeholder={defaultBaseUrl}
				hint={hint}
			/>
			<ApiKeyField
				value={apiKey}
				onChange={setApiKey}
				label={isApiKeyOptional ? t("mc_api_key_opt") : t("mc_api_key")}
				placeholder={t("mc_enter_key")}
			/>
		</div>
	);
}
