"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
	adminCreditsApiService,
	type ManualCreditAdjustPayload,
} from "@/lib/apis/admin-credits-api.service";

interface ManualCreditModalProps {
	isOpen: boolean;
	onClose: () => void;
	onSuccess: () => void;
}

function generateIdempotencyKey(): string {
	const cryptoObj: Crypto | undefined = typeof crypto !== "undefined" ? crypto : undefined;
	if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
		return cryptoObj.randomUUID();
	}
	if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
		const bytes = new Uint8Array(16);
		cryptoObj.getRandomValues(bytes);
		bytes[6] = (bytes[6] & 0x0f) | 0x40;
		bytes[8] = (bytes[8] & 0x3f) | 0x80;
		const parts: string[] = [];
		for (let i = 0; i < 16; i++) {
			const hex = bytes[i].toString(16).padStart(2, "0");
			parts.push([8, 13, 18, 23].includes(i) ? `-${hex}` : hex);
		}
		return parts.join("");
	}
	// ponytail: last-resort fallback for legacy/non-secure contexts. Collision
	// risk is low for single user double-clicks but not suitable for bulk use.
	return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function ManualCreditModal({ isOpen, onClose, onSuccess }: ManualCreditModalProps) {
	const [form, setForm] = useState<ManualCreditAdjustPayload>({
		workspace_id: 0,
		amount_credits: 0,
		direction: "CREDIT",
		reason: "",
		ticket_ref: "",
	});
	const [error, setError] = useState<string | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [idempotencyKey, setIdempotencyKey] = useState<string>(generateIdempotencyKey);

	useEffect(() => {
		if (!isOpen) {
			return;
		}
		setIdempotencyKey(generateIdempotencyKey());
		setError(null);
		setForm({
			workspace_id: 0,
			amount_credits: 0,
			direction: "CREDIT",
			reason: "",
			ticket_ref: "",
		});
	}, [isOpen]);

	const usdValue = useMemo(() => {
		return (form.amount_credits / 100).toFixed(2);
	}, [form.amount_credits]);

	const validate = useCallback((): string | null => {
		if (form.workspace_id <= 0) {
			return "Workspace ID must be a positive integer.";
		}
		if (!Number.isInteger(form.amount_credits) || form.amount_credits <= 0) {
			return "Amount credits must be a positive integer.";
		}
		if (form.reason.length < 10) {
			return "Reason must be at least 10 characters.";
		}
		if (!form.ticket_ref.trim()) {
			return "Ticket reference is required.";
		}
		return null;
	}, [form]);

	const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		setError(null);

		const validationError = validate();
		if (validationError) {
			setError(validationError);
			return;
		}

		setIsSubmitting(true);
		try {
			await adminCreditsApiService.adjust(form, idempotencyKey);
			onSuccess();
			onClose();
			setForm({
				workspace_id: 0,
				amount_credits: 0,
				direction: "CREDIT",
				reason: "",
				ticket_ref: "",
			});
		} catch (err) {
			const message = err instanceof Error ? err.message : "Failed to submit adjustment.";
			setError(message);
		} finally {
			setIsSubmitting(false);
		}
	};

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
			<div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl dark:bg-slate-900">
				<h2 className="mb-4 text-xl font-bold">Manual Credit Adjustment</h2>

				<form onSubmit={handleSubmit} className="space-y-4">
					<div>
						<label htmlFor="manual-credit-workspace" className="mb-1 block text-sm font-medium">
							Workspace ID
						</label>
						<input
							id="manual-credit-workspace"
							type="number"
							min={1}
							required
							className="w-full rounded border p-2 font-mono text-sm"
							value={form.workspace_id || ""}
							onChange={(e) =>
								setForm((prev) => ({
									...prev,
									workspace_id: parseInt(e.target.value, 10) || 0,
								}))
							}
						/>
					</div>

					<div>
						<label htmlFor="manual-credit-direction" className="mb-1 block text-sm font-medium">
							Direction
						</label>
						<select
							id="manual-credit-direction"
							className="w-full rounded border p-2 text-sm"
							value={form.direction}
							onChange={(e) =>
								setForm((prev) => ({
									...prev,
									direction: e.target.value as "CREDIT" | "DEBIT",
								}))
							}
						>
							<option value="CREDIT">CREDIT (top-up)</option>
							<option value="DEBIT">DEBIT (clawback)</option>
						</select>
					</div>

					<div>
						<label htmlFor="manual-credit-amount" className="mb-1 block text-sm font-medium">
							Amount (Credits)
						</label>
						<input
							id="manual-credit-amount"
							type="number"
							min={1}
							required
							className="w-full rounded border p-2 font-mono text-sm"
							value={form.amount_credits || ""}
							onChange={(e) =>
								setForm((prev) => ({
									...prev,
									amount_credits: parseInt(e.target.value, 10) || 0,
								}))
							}
						/>
						<p className="mt-1 text-sm text-slate-500">Preview: ${usdValue} USD</p>
					</div>

					<div>
						<label htmlFor="manual-credit-reason" className="mb-1 block text-sm font-medium">
							Reason
						</label>
						<textarea
							id="manual-credit-reason"
							required
							minLength={10}
							className="w-full rounded border p-2 text-sm"
							rows={3}
							value={form.reason}
							onChange={(e) => setForm((prev) => ({ ...prev, reason: e.target.value }))}
						/>
					</div>

					<div>
						<label htmlFor="manual-credit-ticket" className="mb-1 block text-sm font-medium">
							Ticket / Bank Ref
						</label>
						<input
							id="manual-credit-ticket"
							type="text"
							required
							className="w-full rounded border p-2 text-sm"
							value={form.ticket_ref}
							onChange={(e) => setForm((prev) => ({ ...prev, ticket_ref: e.target.value }))}
						/>
					</div>

					{error && <div className="rounded bg-red-50 p-2 text-sm text-red-600">{error}</div>}

					<div className="flex justify-end gap-2 pt-2">
						<button
							type="button"
							onClick={onClose}
							className="rounded border px-4 py-2 text-sm hover:bg-slate-50"
						>
							Cancel
						</button>
						<button
							type="submit"
							disabled={isSubmitting}
							className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
						>
							{isSubmitting ? "Submitting..." : "Submit Adjustment"}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
}
