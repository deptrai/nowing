"use client";

import { AlertTriangle, Check, Loader2, Send, X } from "lucide-react";
import { useState } from "react";
import { znsSendRequestSchema } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn } from "@/lib/utils";

export interface ZnsSendModalProps {
	leadId: string;
	workspaceId: number | string;
	companyName?: string;
	phone?: string | null;
	onClose: () => void;
}

export const ZnsSendModal: React.FC<ZnsSendModalProps> = ({
	leadId,
	workspaceId,
	companyName = "Khách hàng",
	phone,
	onClose,
}) => {
	const [templateId, setTemplateId] = useState("");
	const [templateDataRaw, setTemplateDataRaw] = useState("{}");
	const [mode, setMode] = useState("");
	const [oaId, setOaId] = useState("");
	const [consent, setConsent] = useState(false);
	const [loading, setLoading] = useState(false);
	const [result, setResult] = useState<{
		status: string;
		msg_id?: string | null;
		error?: string | null;
	} | null>(null);
	const [error, setError] = useState<string | null>(null);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!consent) {
			setError(
				"Bạn phải xác nhận đã nhận được sự đồng ý từ người dùng trước khi gửi ZNS (Decree 356)."
			);
			return;
		}

		let templateData: Record<string, unknown>;
		try {
			templateData = JSON.parse(templateDataRaw);
		} catch {
			setError("Template data phải là JSON object hợp lệ.");
			return;
		}

		const payload = {
			template_id: templateId.trim(),
			template_data: templateData,
			consent_confirmed: true,
			mode: mode.trim() || undefined,
			oa_id: oaId.trim() || undefined,
		};

		const parsed = znsSendRequestSchema.safeParse(payload);
		if (!parsed.success) {
			setError(parsed.error.issues.map((err) => err.message).join("; "));
			return;
		}

		setLoading(true);
		setError(null);
		setResult(null);
		try {
			const res = await leadsApiService.sendZns(workspaceId, leadId, parsed.data);
			setResult(res);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Gửi ZNS thất bại");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
			<button
				type="button"
				aria-label="Đóng cửa sổ"
				className="fixed inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
				onClick={onClose}
			/>
			<div
				role="dialog"
				aria-modal="true"
				className="relative z-10 w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 p-5 space-y-4 shadow-2xl animate-in zoom-in-95 duration-200"
			>
				<div className="flex items-center justify-between border-b border-zinc-800 pb-3">
					<div>
						<h3 className="text-sm font-bold text-zinc-100 flex items-center gap-1.5">
							<span>Gửi ZNS</span>
							<span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-mono">
								Decree 356
							</span>
						</h3>
						<p className="text-xs text-zinc-400">
							Tới: <strong className="text-zinc-200">{companyName}</strong> (
							{phone || "Chưa có SĐT"})
						</p>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700"
					>
						<X className="w-3.5 h-3.5" />
					</button>
				</div>

				{result ? (
					<div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 space-y-2">
						<div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
							{result.status === "sent" ? (
								<>
									<Check className="w-4 h-4 text-emerald-400" />
									<span>Đã gửi ZNS</span>
								</>
							) : (
								<>
									<AlertTriangle className="w-4 h-4 text-red-400" />
									<span>Gửi thất bại</span>
								</>
							)}
						</div>
						{result.msg_id && <p className="text-xs text-zinc-400">msg_id: {result.msg_id}</p>}
						{result.error && <p className="text-xs text-red-400">{result.error}</p>}
					</div>
				) : (
					<form onSubmit={handleSubmit} className="space-y-3">
						<div className="space-y-1">
							<label htmlFor="zns-template-id" className="text-xs font-semibold text-zinc-300">
								Template ID
							</label>
							<input
								id="zns-template-id"
								type="text"
								value={templateId}
								onChange={(e) => setTemplateId(e.target.value)}
								className="w-full p-2.5 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
								placeholder="tpl_appointment_01"
								required
							/>
						</div>

						<div className="space-y-1">
							<label htmlFor="zns-template-data" className="text-xs font-semibold text-zinc-300">
								Template data (JSON)
							</label>
							<textarea
								id="zns-template-data"
								value={templateDataRaw}
								onChange={(e) => setTemplateDataRaw(e.target.value)}
								rows={4}
								className="w-full p-2.5 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none font-mono"
								placeholder='{"name":"Nguyễn Văn A"}'
								required
							/>
						</div>

						<div className="grid grid-cols-2 gap-3">
							<div className="space-y-1">
								<label htmlFor="zns-mode" className="text-xs font-semibold text-zinc-300">
									Mode (tùy chọn)
								</label>
								<input
									id="zns-mode"
									type="text"
									value={mode}
									onChange={(e) => setMode(e.target.value)}
									className="w-full p-2.5 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
									placeholder="development"
								/>
							</div>
							<div className="space-y-1">
								<label htmlFor="zns-oa-id" className="text-xs font-semibold text-zinc-300">
									OA ID (tùy chọn)
								</label>
								<input
									id="zns-oa-id"
									type="text"
									value={oaId}
									onChange={(e) => setOaId(e.target.value)}
									className="w-full p-2.5 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
									placeholder="Nếu workspace có nhiều OA"
								/>
							</div>
						</div>

						<label className="flex items-start gap-2 p-3 rounded-xl bg-zinc-950 border border-zinc-800 text-xs text-zinc-300 cursor-pointer">
							<input
								type="checkbox"
								checked={consent}
								onChange={(e) => setConsent(e.target.checked)}
								className="mt-0.5"
							/>
							<span>
								Tôi xác nhận đã nhận được sự đồng ý rõ ràng từ người dùng này để gửi tin nhắn ZNS
								theo quy định Decree 356.
							</span>
						</label>

						{error && <p className="text-xs text-red-400">{error}</p>}

						<div className="flex justify-end pt-2 border-t border-zinc-800">
							<button
								type="submit"
								disabled={loading}
								className={cn(
									"inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-all shadow-md shadow-blue-500/20",
									"disabled:opacity-50 disabled:cursor-not-allowed"
								)}
							>
								{loading ? (
									<Loader2 className="w-3.5 h-3.5 animate-spin" />
								) : (
									<Send className="w-3.5 h-3.5" />
								)}
								<span>{loading ? "Đang gửi..." : "Gửi ZNS"}</span>
							</button>
						</div>
					</form>
				)}
			</div>
		</div>
	);
};
