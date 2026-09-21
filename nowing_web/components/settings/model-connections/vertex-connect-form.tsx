import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	type ProviderConnectFormProps,
	VERTEX_AUTH_SERVICE_ACCOUNT,
	VERTEX_AUTH_WORKLOAD_IDENTITY,
	VERTEX_DEFAULT_LOCATION,
} from "./provider-metadata";

/**
 * Google Vertex AI (Gemini) connect form. Service-account auth uploads a
 * credentials JSON file (read into a string); workload identity collects a
 * project id. Credentials ride along in `extra.litellm_params`.
 */
export function VertexConnectForm({ onDraftChange }: ProviderConnectFormProps) {
	const t = useTranslations("settings");
	const [authMethod, setAuthMethod] = useState(VERTEX_AUTH_SERVICE_ACCOUNT);
	const [location, setLocation] = useState(VERTEX_DEFAULT_LOCATION);
	const [credentials, setCredentials] = useState("");
	const [project, setProject] = useState("");

	const canSubmit =
		authMethod === VERTEX_AUTH_SERVICE_ACCOUNT ? Boolean(credentials) : Boolean(project);

	async function handleCredentialsFile(file: File | undefined) {
		if (!file) return;
		setCredentials(await file.text());
	}

	useEffect(() => {
		const params: Record<string, string> = {};
		if (location) params.vertex_location = location;
		if (authMethod === VERTEX_AUTH_SERVICE_ACCOUNT) {
			if (credentials) params.vertex_credentials = credentials;
		} else if (project) {
			params.vertex_project = project;
		}
		onDraftChange({ base_url: null, api_key: null, extra: { litellm_params: params } }, canSubmit);
	}, [authMethod, canSubmit, credentials, location, onDraftChange, project]);

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Label>{t("mc_auth_method")}</Label>
				<Select value={authMethod} onValueChange={setAuthMethod}>
					<SelectTrigger>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value={VERTEX_AUTH_SERVICE_ACCOUNT}>{t("mc_service_account")}</SelectItem>
						<SelectItem value={VERTEX_AUTH_WORKLOAD_IDENTITY}>
							{t("mc_workload_identity")}
						</SelectItem>
					</SelectContent>
				</Select>
			</div>
			<div className="flex flex-col gap-2">
				<Label>{t("mc_gcp_region")}</Label>
				<Input
					value={location}
					onChange={(event) => setLocation(event.target.value)}
					placeholder={VERTEX_DEFAULT_LOCATION}
				/>
				<p className="text-xs text-muted-foreground">{t("mc_gcp_region_desc")}</p>
			</div>
			{authMethod === VERTEX_AUTH_SERVICE_ACCOUNT ? (
				<div className="flex flex-col gap-2">
					<Label>{t("mc_service_account")}</Label>
					<Input
						id="vertex-service-account-json"
						type="file"
						accept="application/json,.json"
						className="sr-only"
						onChange={(event) => handleCredentialsFile(event.target.files?.[0])}
					/>
					<Label
						htmlFor="vertex-service-account-json"
						className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/40 bg-muted/20 px-4 py-6 text-center transition-colors hover:border-muted-foreground/70 hover:bg-muted/40"
					>
						<span className="text-sm font-medium">
							{credentials ? t("mc_json_selected") : t("mc_upload_json")}
						</span>
						<span className="text-xs text-muted-foreground">{t("mc_choose_json")}</span>
					</Label>
					<p className="text-xs text-muted-foreground">
						{credentials ? t("mc_creds_loaded") : t("mc_attach_creds")}
					</p>
				</div>
			) : (
				<div className="flex flex-col gap-2">
					<Label>{t("mc_gcp_project")}</Label>
					<Input
						value={project}
						onChange={(event) => setProject(event.target.value)}
						placeholder="my-vertex-project"
					/>
					<p className="text-xs text-muted-foreground">{t("mc_gcp_project_desc")}</p>
				</div>
			)}
			<p className="text-xs text-muted-foreground">{t("mc_add_after")}</p>
		</div>
	);
}
