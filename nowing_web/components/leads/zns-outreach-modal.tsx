"use client";

import {
	AlertTriangle,
	CheckCircle2,
	Clock,
	Info,
	Loader2,
	Phone,
	Send,
	ShieldAlert,
	Smartphone,
	X,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";
import { type ZnsTemplate, znsApiService } from "@/lib/apis/zns-api.service";
import { cn } from "@/lib/utils";

export interface ZnsOutreachModalProps {
	leadId?: string;
	workspaceId: number | string;
	customerName?: string;
	phone?: string | null;
	propertyName?: string;
	priceEstimate?: string;
	consultantPhone?: string;
	isDncBlocked?: boolean;
	onClose: () => void;
	onSuccess?: () => void;
}

export const ZnsOutreachModal: React.FC<ZnsOutreachModalProps> = ({
	leadId,
	workspaceId,
	customerName = "Quý khách",
	phone = "",
	propertyName = "Dự án cao cấp",
	priceEstimate = "Thỏa thuận",
	consultantPhone = "0901234567",
	isDncBlocked = false,
	onClose,
	onSuccess,
}) => {
	const [templates, setTemplates] = useState<ZnsTemplate[]>([]);
	const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
	const [formValues, setFormValues] = useState<Record<string, string>>({
		customer_name: customerName,
		property_name: propertyName,
		price: priceEstimate,
		consultant_phone: consultantPhone,
	});
	const [recipientPhone, setRecipientPhone] = useState<string>(phone || "");
	const [loading, setLoading] = useState<boolean>(false);
	const [fetchingTemplates, setFetchingTemplates] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);
	const [successMsg, setSuccessMsg] = useState<string | null>(null);

	// Check legal sending window (08:00 - 21:30 VN Time per Decree 91)
	const isSendingWindowOpen = useMemo(() => {
		const now = new Date();
		// Compute Vietnam time UTC+7
		const utc = now.getTime() + now.getTimezoneOffset() * 60000;
		const vnTime = new Date(utc + 3600000 * 7);
		const minutes = vnTime.getHours() * 60 + vnTime.getMinutes();
		return minutes >= 8 * 60 && minutes <= 21 * 60 + 30;
	}, []);

	useEffect(() => {
		let isMounted = true;
		const loadTemplates = async () => {
			try {
				const list = await znsApiService.listTemplates(workspaceId);
				if (isMounted && list && list.length > 0) {
					setTemplates(list);
					setSelectedTemplateId(list[0].template_id);
				}
			} catch (err) {
				console.warn("Failed to load ZNS templates:", err);
			} finally {
				if (isMounted) setFetchingTemplates(false);
			}
		};
		loadTemplates();
		return () => {
			isMounted = false;
		};
	}, [workspaceId]);

	const selectedTemplate = useMemo(() => {
		return templates.find((t) => t.template_id === selectedTemplateId) || templates[0];
	}, [templates, selectedTemplateId]);

	// Update form values when selected template changes (UI-01)
	useEffect(() => {
		if (!selectedTemplate) return;
		const schemaKeys =
			selectedTemplate.schema && selectedTemplate.schema.length > 0
				? selectedTemplate.schema
				: Object.keys(selectedTemplate.sample_data || {});

		setFormValues((prev) => {
			const updated: Record<string, string> = {};
			for (const key of schemaKeys) {
				if (key === "customer_name") {
					updated[key] = prev[key] || customerName;
				} else if (key === "property_name") {
					updated[key] = prev[key] || propertyName;
				} else if (key === "price") {
					updated[key] = prev[key] || priceEstimate;
				} else if (key === "consultant_phone") {
					updated[key] = prev[key] || consultantPhone;
				} else {
					updated[key] = prev[key] || String(selectedTemplate.sample_data?.[key] || "");
				}
			}
			return updated;
		});
	}, [selectedTemplate, customerName, propertyName, priceEstimate, consultantPhone]);

	const handleInputChange = (key: string, value: string) => {
		setFormValues((prev) => ({ ...prev, [key]: value }));
	};

	const handleSend = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!recipientPhone.trim()) {
			setError("Vui lòng nhập số điện thoại người nhận");
			return;
		}
		if (isDncBlocked) {
			setError("Số điện thoại này thuộc danh sách Từ chối cuộc gọi/tin nhắn (DNC). Không thể gửi.");
			return;
		}
		if (!isSendingWindowOpen) {
			setError(
				"Nghị định 91/2020/NĐ-CP cấm gửi tin nhắn ngoài khung giờ 08:00 – 21:30 (Giờ Việt Nam)."
			);
			return;
		}

		setLoading(true);
		setError(null);
		setSuccessMsg(null);

		try {
			const res = await znsApiService.sendZns(workspaceId, {
				lead_id: leadId,
				phone: recipientPhone.trim(),
				template_id: selectedTemplate?.template_id || selectedTemplateId,
				template_data: formValues,
			});
			setSuccessMsg(`Đã gửi ZNS thành công (Mã tin: ${res.msg_id})`);
			if (onSuccess) onSuccess();
		} catch (err: unknown) {
			setError(err instanceof Error ? err.message : "Gửi ZNS thất bại");
		} finally {
			setLoading(false);
		}
	};

	const templateSchemaKeys = useMemo(() => {
		if (selectedTemplate?.schema && selectedTemplate.schema.length > 0) {
			return selectedTemplate.schema;
		}
		return Object.keys(formValues);
	}, [selectedTemplate, formValues]);

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
			<button
				type="button"
				aria-label="Đóng"
				className="fixed inset-0 bg-black/75 backdrop-blur-sm"
				onClick={onClose}
			/>

			<div
				data-testid="zns-outreach-modal"
				role="dialog"
				aria-modal="true"
				className="relative z-10 w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-2xl bg-zinc-950 border border-zinc-800 shadow-2xl flex flex-col animate-in zoom-in-95 duration-200"
			>
				{/* Modal Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/60">
					<div className="flex items-center gap-3">
						<div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-sm">
							⚡
						</div>
						<div>
							<h3 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
								<span>Gửi ZNS Outreach</span>
								<span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
									Zalo OpenAPI v3
								</span>
							</h3>
							<p className="text-xs text-zinc-400">
								Gửi mẫu tin nhắn thông báo chính thức có tích hợp chữ ký HMAC & chống spam
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 rounded-lg transition-colors"
					>
						<X className="w-5 h-5" aria-hidden="true" />
					</button>
				</div>

				{/* Compliance Warning Banner */}
				{!isSendingWindowOpen && (
					<div className="bg-amber-950/40 border-b border-amber-800/40 px-6 py-2.5 flex items-center gap-2 text-xs text-amber-300">
						<Clock className="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
						<span>
							<strong>Khung giờ gửi hạn chế:</strong> Đang ngoài khung giờ hợp lệ 08:00 – 21:30
							(Nghị định 91/2020/NĐ-CP). Tính năng gửi tạm khóa.
						</span>
					</div>
				)}

				{isDncBlocked && (
					<div className="bg-rose-950/40 border-b border-rose-800/40 px-6 py-2.5 flex items-center gap-2 text-xs text-rose-300">
						<ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" aria-hidden="true" />
						<span>
							<strong>Cảnh báo DNC Blacklist:</strong> Số điện thoại này nằm trong danh sách không
							nhận cuộc gọi/quảng cáo.
						</span>
					</div>
				)}

				{/* Split-Pane Body */}
				<div className="grid grid-cols-1 md:grid-cols-12 flex-1 overflow-y-auto min-h-[440px]">
					{/* Left Pane: Form Controls (7 cols) */}
					<form
						onSubmit={handleSend}
						className="md:col-span-7 p-6 border-b md:border-b-0 md:border-r border-zinc-800 space-y-4"
					>
						{/* Phone Number Input */}
						<div>
							<label
								htmlFor="zns-recipient-phone"
								className="block text-xs font-medium text-zinc-300 mb-1.5"
							>
								Số điện thoại người nhận
							</label>
							<div className="relative">
								<Phone
									className="w-4 h-4 absolute left-3 top-2.5 text-zinc-500"
									aria-hidden="true"
								/>
								<input
									id="zns-recipient-phone"
									type="text"
									name="recipient_phone"
									value={recipientPhone}
									onChange={(e) => setRecipientPhone(e.target.value)}
									placeholder="0912345678"
									className="w-full bg-zinc-900 border border-zinc-800 rounded-xl pl-9 pr-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-blue-500 transition-colors"
								/>
							</div>
						</div>

						{/* Template Selector */}
						<div>
							<label
								htmlFor="zns-template-select-input"
								className="block text-xs font-medium text-zinc-300 mb-1.5"
							>
								Mẫu tin nhắn ZNS (Template)
							</label>
							<select
								id="zns-template-select-input"
								data-testid="zns-template-select"
								value={selectedTemplateId}
								onChange={(e) => setSelectedTemplateId(e.target.value)}
								disabled={fetchingTemplates || templates.length === 0}
								className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-blue-500 transition-colors"
							>
								{templates.map((t) => (
									<option key={t.template_id} value={t.template_id}>
										{t.template_name} ({t.template_id})
									</option>
								))}
							</select>
						</div>

						{/* Dynamic Parameter Inputs (UI-01) */}
						<div className="space-y-3 pt-1">
							<span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block">
								Biến động mẫu tin (Parameters)
							</span>

							{templateSchemaKeys.map((key) => (
								<div key={key}>
									<label htmlFor={`param-${key}`} className="block text-[11px] text-zinc-400 mb-1">
										Biến &#123;{key}&#125;
									</label>
									<input
										id={`param-${key}`}
										type="text"
										name={key}
										value={formValues[key] || ""}
										onChange={(e) => handleInputChange(key, e.target.value)}
										placeholder={`Nhập ${key}...`}
										className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-blue-500"
									/>
								</div>
							))}
						</div>

						{/* Cost & Quota Estimator */}
						<div className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800/80 flex items-center justify-between text-xs">
							<div className="flex items-center gap-2 text-zinc-400">
								<Info className="w-4 h-4 text-blue-400" aria-hidden="true" />
								<span>Chi phí tin nhắn:</span>
							</div>
							<div className="font-semibold text-zinc-100 flex items-center gap-1.5">
								<span className="text-emerald-400">300đ</span>
								<span className="text-zinc-500">(0.3 credits)</span>
							</div>
						</div>

						{error && (
							<div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/40 text-xs text-rose-300 flex items-start gap-2">
								<AlertTriangle
									className="w-4 h-4 text-rose-400 shrink-0 mt-0.5"
									aria-hidden="true"
								/>
								<span>{error}</span>
							</div>
						)}

						{successMsg && (
							<div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/40 text-xs text-emerald-300 flex items-center gap-2">
								<CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
								<span>{successMsg}</span>
							</div>
						)}

						<div className="pt-2">
							<button
								type="submit"
								disabled={loading || isDncBlocked || !isSendingWindowOpen}
								className={cn(
									"w-full py-2.5 px-4 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition-all",
									loading || isDncBlocked || !isSendingWindowOpen
										? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
										: "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20"
								)}
							>
								{loading ? (
									<>
										<Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
										<span>Đang gửi qua Zalo OA...</span>
									</>
								) : (
									<>
										<Send className="w-4 h-4" aria-hidden="true" />
										<span>Gửi ZNS Template</span>
									</>
								)}
							</button>
						</div>
					</form>

					{/* Right Pane: Simulated Mobile Viewport Mockup (5 cols) */}
					<div
						data-testid="zns-mobile-mockup"
						className="md:col-span-5 p-6 bg-zinc-950/50 flex flex-col items-center justify-center"
					>
						<span className="text-xs text-zinc-400 font-medium mb-3 flex items-center gap-1.5">
							<Smartphone className="w-4 h-4 text-zinc-400" aria-hidden="true" />
							<span>Xem trước trên Zalo mobile</span>
						</span>

						{/* Phone Shell */}
						<div className="w-[280px] rounded-[32px] border-4 border-zinc-800 bg-zinc-900 p-3 shadow-2xl relative overflow-hidden">
							{/* Notch */}
							<div className="w-24 h-4 bg-zinc-800 rounded-full mx-auto mb-3" />

							{/* Zalo Notification Card */}
							<div className="rounded-2xl bg-white text-zinc-900 overflow-hidden shadow-md text-left">
								{/* Zalo Header */}
								<div className="bg-[#0068FF] px-3.5 py-2.5 text-white flex items-center justify-between">
									<div className="flex items-center gap-1.5">
										<div className="w-5 h-5 rounded-full bg-white text-[#0068FF] font-bold text-[10px] flex items-center justify-center">
											Z
										</div>
										<span className="text-xs font-semibold tracking-tight">
											Zalo Notification Service
										</span>
									</div>
									<span className="text-[10px] text-blue-100">OA Verified</span>
								</div>

								{/* Message Content */}
								<div className="p-3.5 space-y-2 text-xs">
									<div className="font-semibold text-zinc-900 text-sm">
										{selectedTemplate?.template_name || "Thông báo thông tin bất động sản"}
									</div>

									<p className="text-zinc-600 text-[11px] leading-relaxed">
										Kính gửi <strong>{formValues.customer_name || "Quý khách"}</strong>, Nowing xin
										gửi thông tin chi tiết về nội dung bạn đang quan tâm:
									</p>

									<div className="bg-zinc-50 border border-zinc-100 rounded-lg p-2.5 space-y-1.5 text-[11px]">
										{templateSchemaKeys
											.filter((k) => k !== "customer_name")
											.map((k) => (
												<div key={k} className="flex justify-between">
													<span className="text-zinc-500 capitalize">{k.replace(/_/g, " ")}:</span>
													<span className="font-semibold text-zinc-800">
														{formValues[k] || "---"}
													</span>
												</div>
											))}
									</div>

									{/* CTA Button */}
									<div className="pt-1">
										<div className="w-full py-2 bg-[#0068FF] text-white text-center rounded-lg font-medium text-xs shadow-sm">
											Xem chi tiết
										</div>
									</div>
								</div>
							</div>

							{/* Bottom bar indicator */}
							<div className="w-16 h-1 bg-zinc-700 rounded-full mx-auto mt-4" />
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};
