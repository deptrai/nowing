import { Cpu, Shuffle } from "lucide-react";
import {
	Ai21Icon,
	AnyscaleIcon,
	AzureIcon,
	BedrockIcon,
	CerebrasIcon,
	ClaudeIcon,
	CloudflareIcon,
	CohereIcon,
	CometApiIcon,
	DatabricksIcon,
	DeepInfraIcon,
	DeepSeekIcon,
	FireworksAiIcon,
	GeminiIcon,
	GitHubModelsIcon,
	GroqIcon,
	HuggingFaceIcon,
	LmStudioIcon,
	MiniMaxIcon,
	MistralIcon,
	MoonshotIcon,
	NscaleIcon,
	OllamaIcon,
	OpenaiIcon,
	OpenRouterIcon,
	PerplexityIcon,
	QwenIcon,
	RecraftIcon,
	ReplicateIcon,
	RequestyIcon,
	SambaNovaIcon,
	TogetherAiIcon,
	VertexAiIcon,
	XaiIcon,
	XinferenceIcon,
	ZhipuIcon,
} from "@/components/icons/providers";
import { cn } from "@/lib/utils";

export const AUTO_PROVIDER_ICON_KEY = "AUTO";

/**
 * Returns a Lucide icon element for the given LLM / image-gen provider.
 * Accepts an optional `className` override for the icon size.
 */
export function getProviderIcon(
	provider: string,
	{ isAutoMode, className = "size-4" }: { isAutoMode?: boolean; className?: string } = {}
) {
	if (isAutoMode || provider?.toUpperCase() === AUTO_PROVIDER_ICON_KEY) {
		return <Shuffle className={cn(className, "text-muted-foreground")} aria-hidden="true" />;
	}

	switch (provider?.toUpperCase()) {
		case "AI21":
			return <Ai21Icon className={cn(className)} aria-hidden="true" />;
		case "ALIBABA_QWEN":
			return <QwenIcon className={cn(className)} aria-hidden="true" />;
		case "ANTHROPIC":
		case "CLAUDE":
			return <ClaudeIcon className={cn(className)} aria-hidden="true" />;
		case "ANYSCALE":
			return <AnyscaleIcon className={cn(className)} aria-hidden="true" />;
		case "AZURE":
		case "AZURE_OPENAI":
			return <AzureIcon className={cn(className)} aria-hidden="true" />;
		case "AWS_BEDROCK":
		case "BEDROCK":
			return <BedrockIcon className={cn(className)} aria-hidden="true" />;
		case "CEREBRAS":
			return <CerebrasIcon className={cn(className)} aria-hidden="true" />;
		case "CLOUDFLARE":
			return <CloudflareIcon className={cn(className)} aria-hidden="true" />;
		case "COHERE":
			return <CohereIcon className={cn(className)} aria-hidden="true" />;
		case "COMETAPI":
			return <CometApiIcon className={cn(className)} aria-hidden="true" />;
		case "CUSTOM":
			return <Cpu className={cn(className)} aria-hidden="true" />;
		case "DATABRICKS":
			return <DatabricksIcon className={cn(className)} aria-hidden="true" />;
		case "DEEPINFRA":
			return <DeepInfraIcon className={cn(className)} aria-hidden="true" />;
		case "DEEPSEEK":
			return <DeepSeekIcon className={cn(className)} aria-hidden="true" />;
		case "FIREWORKS_AI":
			return <FireworksAiIcon className={cn(className)} aria-hidden="true" />;
		case "GOOGLE":
			return <GeminiIcon className={cn(className)} aria-hidden="true" />;
		case "GITHUB_MODELS":
			return <GitHubModelsIcon className={cn(className)} aria-hidden="true" />;
		case "GROQ":
			return <GroqIcon className={cn(className)} aria-hidden="true" />;
		case "HUGGINGFACE":
			return <HuggingFaceIcon className={cn(className)} aria-hidden="true" />;
		case "LM_STUDIO":
			return <LmStudioIcon className={cn(className)} aria-hidden="true" />;
		case "MINIMAX":
			return <MiniMaxIcon className={cn(className)} aria-hidden="true" />;
		case "MISTRAL":
			return <MistralIcon className={cn(className)} aria-hidden="true" />;
		case "MOONSHOT":
			return <MoonshotIcon className={cn(className)} aria-hidden="true" />;
		case "NSCALE":
			return <NscaleIcon className={cn(className)} aria-hidden="true" />;
		case "OLLAMA":
		case "OLLAMA_CHAT":
			return <OllamaIcon className={cn(className)} aria-hidden="true" />;
		case "OPENAI":
			return <OpenaiIcon className={cn(className)} aria-hidden="true" />;
		case "OPENROUTER":
			return <OpenRouterIcon className={cn(className)} aria-hidden="true" />;
		case "PERPLEXITY":
			return <PerplexityIcon className={cn(className)} aria-hidden="true" />;
		case "RECRAFT":
			return <RecraftIcon className={cn(className)} aria-hidden="true" />;
		case "REPLICATE":
			return <ReplicateIcon className={cn(className)} aria-hidden="true" />;
		case "REQUESTY":
			return <RequestyIcon className={cn(className)} aria-hidden="true" />;
		case "SAMBANOVA":
			return <SambaNovaIcon className={cn(className)} aria-hidden="true" />;
		case "TOGETHER_AI":
			return <TogetherAiIcon className={cn(className)} aria-hidden="true" />;
		case "VERTEX_AI":
			return <VertexAiIcon className={cn(className)} aria-hidden="true" />;
		case "XAI":
			return <XaiIcon className={cn(className)} aria-hidden="true" />;
		case "XINFERENCE":
			return <XinferenceIcon className={cn(className)} aria-hidden="true" />;
		case "ZHIPU":
			return <ZhipuIcon className={cn(className)} aria-hidden="true" />;
		default:
			return <Cpu className={cn(className, "text-muted-foreground")} aria-hidden="true" />;
	}
}
