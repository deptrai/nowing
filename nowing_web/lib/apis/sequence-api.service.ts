import { z } from "zod";
import {
	type Sequence,
	type SequenceAnalytics,
	type SequenceCreate,
	type SequenceEnrollment,
	type SequenceEvent,
	sequenceAnalyticsSchema,
	sequenceEnrollmentSchema,
	sequenceEventSchema,
	sequenceSchema,
} from "@/contracts/types/sequence.types";
import { baseApiService } from "./base-api.service";

const base = (workspaceId: number | string) => `/workspaces/${workspaceId}/sequences`;

class SequenceApiService {
	listSequences = async (workspaceId: number | string): Promise<Sequence[]> => {
		return baseApiService.get(base(workspaceId), z.array(sequenceSchema));
	};

	getSequence = async (workspaceId: number | string, sequenceId: string): Promise<Sequence> => {
		return baseApiService.get(`${base(workspaceId)}/${sequenceId}`, sequenceSchema);
	};

	createSequence = async (
		workspaceId: number | string,
		payload: SequenceCreate
	): Promise<Sequence> => {
		return baseApiService.post(base(workspaceId), sequenceSchema, {
			body: payload,
		});
	};

	updateSequence = async (
		workspaceId: number | string,
		sequenceId: string,
		payload: Partial<SequenceCreate>
	): Promise<Sequence> => {
		return baseApiService.put(`${base(workspaceId)}/${sequenceId}`, sequenceSchema, {
			body: payload,
		});
	};

	deleteSequence = async (workspaceId: number | string, sequenceId: string): Promise<void> => {
		return baseApiService.delete(`${base(workspaceId)}/${sequenceId}`);
	};

	enrollLeads = async (
		workspaceId: number | string,
		sequenceId: string,
		leadIds: string[]
	): Promise<SequenceEnrollment[]> => {
		return baseApiService.post(
			`${base(workspaceId)}/${sequenceId}/enroll`,
			z.array(sequenceEnrollmentSchema),
			{
				body: { lead_ids: leadIds },
			}
		);
	};

	pauseSequence = async (workspaceId: number | string, sequenceId: string): Promise<Sequence> => {
		return baseApiService.post(`${base(workspaceId)}/${sequenceId}/pause`, sequenceSchema);
	};

	resumeSequence = async (workspaceId: number | string, sequenceId: string): Promise<Sequence> => {
		return baseApiService.post(`${base(workspaceId)}/${sequenceId}/resume`, sequenceSchema);
	};

	getAnalytics = async (
		workspaceId: number | string,
		sequenceId: string
	): Promise<SequenceAnalytics> => {
		return baseApiService.get(
			`${base(workspaceId)}/${sequenceId}/analytics`,
			sequenceAnalyticsSchema
		);
	};

	listEnrollments = async (
		workspaceId: number | string,
		sequenceId: string
	): Promise<SequenceEnrollment[]> => {
		return baseApiService.get(
			`${base(workspaceId)}/${sequenceId}/enrollments`,
			z.array(sequenceEnrollmentSchema)
		);
	};

	listEvents = async (
		workspaceId: number | string,
		sequenceId: string
	): Promise<SequenceEvent[]> => {
		return baseApiService.get(
			`${base(workspaceId)}/${sequenceId}/events`,
			z.array(sequenceEventSchema)
		);
	};
}

export const sequenceApiService = new SequenceApiService();
