import { z } from "zod";
import { baseApiService } from "./base-api.service";

export const znsTemplateSchema = z.object({
	template_id: z.string(),
	template_name: z.string(),
	preview_image: z.string().nullable().optional(),
	price: z.number().default(300),
	schema: z.array(z.string()).default([]),
	sample_data: z.record(z.string(), z.any()).default({}),
	status: z.string().default("APPROVED"),
});

export type ZnsTemplate = z.infer<typeof znsTemplateSchema>;

export const znsSendRequestPayloadSchema = z.object({
	lead_id: z.string().uuid().optional(),
	phone: z.string().min(1, "Số điện thoại không được để trống"),
	template_id: z.string().min(1, "Chưa chọn template"),
	template_data: z.record(z.string(), z.any()).default({}),
});

export type ZnsSendRequestPayload = z.infer<typeof znsSendRequestPayloadSchema>;

export const znsSendResponsePayloadSchema = z.object({
	status: z.string(),
	msg_id: z.string(),
	log_id: z.string().nullable().optional(),
	phone: z.string(),
	template_id: z.string(),
	cost_micros: z.number(),
});

export type ZnsSendResponsePayload = z.infer<typeof znsSendResponsePayloadSchema>;

export const znsLogItemSchema = z.object({
	id: z.number(),
	workspace_id: z.number(),
	lead_id: z.string().uuid().nullable().optional(),
	recipient_phone: z.string().nullable().optional(),
	message_type: z.string(),
	content: z.string().nullable().optional(),
	status: z.string(),
	external_message_id: z.string().nullable().optional(),
	template_data: z.record(z.string(), z.any()).default({}),
	created_at: z.string().nullable().optional(),
});

export type ZnsLogItem = z.infer<typeof znsLogItemSchema>;

const base = (workspaceId: number | string) => `/api/v1/workspaces/${workspaceId}/zns`;

class ZnsApiService {
	listTemplates = async (workspaceId: number | string): Promise<ZnsTemplate[]> => {
		return baseApiService.get(`${base(workspaceId)}/templates`, z.array(znsTemplateSchema));
	};

	sendZns = async (
		workspaceId: number | string,
		payload: ZnsSendRequestPayload
	): Promise<ZnsSendResponsePayload> => {
		return baseApiService.post(`${base(workspaceId)}/send`, znsSendResponsePayloadSchema, {
			body: payload,
		});
	};

	listLogs = async (workspaceId: number | string): Promise<ZnsLogItem[]> => {
		return baseApiService.get(`${base(workspaceId)}/logs`, z.array(znsLogItemSchema));
	};
}

export const znsApiService = new ZnsApiService();
