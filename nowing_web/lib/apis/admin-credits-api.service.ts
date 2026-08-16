"use client";

import { baseApiService } from "./base-api.service";

export interface ManualCreditAdjustPayload {
	workspace_id: number;
	amount_credits: number;
	direction: "CREDIT" | "DEBIT";
	reason: string;
	ticket_ref: string;
}

export interface ManualCreditAdjustResponse {
	transaction_id: number;
	workspace_id: number;
	actor_admin_id: string;
	direction: string;
	amount_credits: number;
	amount_micros: number;
	reason: string;
	ticket_ref: string;
	idempotency_key: string;
	new_balance_credits: number;
	created_at: string | null;
}

export interface ManualCreditLedgerEntry {
	transaction_id: number;
	workspace_id: number;
	actor_admin_id: string;
	direction: string;
	amount_credits: number;
	amount_micros: number;
	reason: string;
	ticket_ref: string;
	created_at: string;
}

export interface ManualCreditLedgerFilters {
	workspace_id?: number;
	admin_id?: string;
	date_from?: string;
	date_to?: string;
	reason?: string;
}

class AdminCreditsApiService {
	adjust = async (
		payload: ManualCreditAdjustPayload,
		idempotencyKey: string
	): Promise<ManualCreditAdjustResponse> => {
		return baseApiService.post("/api/v1/admin/credits/adjust", undefined, {
			body: payload,
			headers: {
				"Idempotency-Key": idempotencyKey,
			},
		});
	};

	ledger = async (filters: ManualCreditLedgerFilters = {}): Promise<ManualCreditLedgerEntry[]> => {
		const params = new URLSearchParams();
		if (filters.workspace_id !== undefined) {
			params.set("workspace_id", String(filters.workspace_id));
		}
		if (filters.admin_id) {
			params.set("admin_id", filters.admin_id);
		}
		if (filters.date_from) {
			params.set("date_from", filters.date_from);
		}
		if (filters.date_to) {
			params.set("date_to", filters.date_to);
		}
		if (filters.reason) {
			params.set("reason", filters.reason);
		}
		const query = params.toString();
		const url = `/api/v1/admin/credits/ledger${query ? `?${query}` : ""}`;
		return baseApiService.get(url);
	};
}

export const adminCreditsApiService = new AdminCreditsApiService();
