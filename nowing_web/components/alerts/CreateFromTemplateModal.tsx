"use client";

import {
	AlertTriangle,
	Building2,
	Clock,
	Layers,
	LineChart,
	Newspaper,
	ShoppingBag,
	Tag,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { AlertRule, AlertTemplateRead } from "@/contracts/types/alert-rules.types";
import { alertRulesApiService } from "@/lib/apis/alert-rules-api.service";

interface CreateFromTemplateModalProps {
	workspaceId: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCreated?: (rule: AlertRule) => void;
}

export default function CreateFromTemplateModal({
	workspaceId,
	open,
	onOpenChange,
	onCreated,
}: CreateFromTemplateModalProps) {
	const [templates, setTemplates] = useState<AlertTemplateRead[]>([]);
	const [loading, setLoading] = useState(false);
	const [selectedTemplate, setSelectedTemplate] = useState<AlertTemplateRead | null>(null);
	const [ruleName, setRuleName] = useState("");
	const [parameters, setParameters] = useState<Record<string, unknown>>({});
	const [schedule, setSchedule] = useState<"daily" | "weekly" | "none">("daily");
	const [submitting, setSubmitting] = useState(false);

	const handleSelectTemplate = useCallback((template: AlertTemplateRead) => {
		setSelectedTemplate(template);
		setRuleName(template.name);
		setSchedule((template.default_schedule as "daily" | "weekly" | "none") || "daily");
		const defaults: Record<string, unknown> = {};
		for (const p of template.parameters) {
			defaults[p.name] = p.default !== undefined ? p.default : "";
		}
		setParameters(defaults);
	}, []);

	useEffect(() => {
		if (open) {
			setLoading(true);
			alertRulesApiService
				.listTemplates(workspaceId)
				.then((items) => {
					setTemplates(items);
					if (items.length > 0 && !selectedTemplate) {
						handleSelectTemplate(items[0]);
					}
				})
				.catch((err) => {
					console.error("Failed to fetch alert templates:", err);
					toast.error("Could not load alert templates");
				})
				.finally(() => setLoading(false));
		}
	}, [open, workspaceId, handleSelectTemplate, selectedTemplate]);

	const handleParamChange = (name: string, value: unknown) => {
		setParameters((prev) => ({ ...prev, [name]: value }));
	};

	const handleCreate = async () => {
		if (!selectedTemplate) return;
		if (!ruleName.trim()) {
			toast.error("Please enter a name for the alert rule");
			return;
		}

		setSubmitting(true);
		try {
			const rule = await alertRulesApiService.createFromTemplate(workspaceId, {
				template_id: selectedTemplate.template_id,
				name: ruleName.trim(),
				parameters,
				schedule,
				notification_channels: ["in_app"],
			});
			toast.success(`Alert "${rule.name}" created successfully!`);
			onCreated?.(rule);
			onOpenChange(false);
		} catch (err: unknown) {
			console.error("Failed to create alert from template:", err);
			const errorMsg =
				err && typeof err === "object" && "message" in err
					? String((err as { message: unknown }).message)
					: "Could not create alert rule";
			toast.error(errorMsg);
		} finally {
			setSubmitting(false);
		}
	};

	const getCategoryIcon = (category: string) => {
		switch (category) {
			case "finance":
				return <LineChart className="h-4 w-4 text-emerald-500" />;
			case "news":
				return <Newspaper className="h-4 w-4 text-sky-500" />;
			case "company":
				return <Building2 className="h-4 w-4 text-amber-500" />;
			case "ecommerce":
				return <ShoppingBag className="h-4 w-4 text-rose-500" />;
			default:
				return <Layers className="h-4 w-4 text-indigo-500" />;
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className="max-w-2xl max-h-[85vh] flex flex-col p-6"
				data-testid="create-alert-template-modal"
			>
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						<Tag className="h-5 w-5 text-primary" />
						Create Alert from Vertical Template
					</DialogTitle>
					<DialogDescription>
						1-Click intelligent monitoring for stocks, news, companies, and e-commerce prices.
					</DialogDescription>
				</DialogHeader>

				{loading ? (
					<div className="py-12 text-center text-sm text-muted-foreground animate-pulse">
						Loading vertical templates...
					</div>
				) : (
					<div className="grid grid-cols-1 md:grid-cols-5 gap-6 py-2 overflow-y-auto">
						{/* Template selector list */}
						<div className="md:col-span-2 space-y-2 border-r pr-4">
							<Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
								Available Templates
							</Label>
							<div className="space-y-1.5">
								{templates.map((tmpl) => {
									const isSelected = selectedTemplate?.template_id === tmpl.template_id;
									return (
										<button
											key={tmpl.template_id}
											type="button"
											disabled={!tmpl.is_available}
											onClick={() => handleSelectTemplate(tmpl)}
											className={`w-full text-left p-2.5 rounded-lg border transition-all flex items-start gap-2.5 ${
												isSelected
													? "border-primary bg-primary/5 shadow-xs"
													: tmpl.is_available
														? "border-border hover:border-primary/50 hover:bg-muted/50"
														: "border-border/40 opacity-60 bg-muted/20 cursor-not-allowed"
											}`}
											data-testid={`template-card-${tmpl.template_id}`}
										>
											<div className="mt-0.5 shrink-0">{getCategoryIcon(tmpl.category)}</div>
											<div className="min-w-0 flex-1">
												<div className="flex items-center justify-between gap-1">
													<p className="text-xs font-semibold truncate">{tmpl.name}</p>
													{!tmpl.is_available && (
														<Badge
															variant="outline"
															className="text-[10px] h-3.5 px-1 text-rose-500 border-rose-200"
														>
															Unavailable
														</Badge>
													)}
												</div>
												<p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
													{tmpl.description}
												</p>
											</div>
										</button>
									);
								})}
							</div>
						</div>

						{/* Form for selected template */}
						{selectedTemplate && (
							<div className="md:col-span-3 space-y-4">
								<div className="space-y-1 border-b pb-3">
									<div className="flex items-center gap-2">
										{getCategoryIcon(selectedTemplate.category)}
										<h4 className="font-semibold text-sm">{selectedTemplate.name}</h4>
									</div>
									<p className="text-xs text-muted-foreground">{selectedTemplate.description}</p>
									<div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground">
										<span>
											Strategy:{" "}
											<code className="text-foreground">{selectedTemplate.diff_strategy}</code>
										</span>
										<span>•</span>
										<span>
											Capability:{" "}
											<code className="text-foreground">
												{selectedTemplate.required_capability}
											</code>
										</span>
									</div>
								</div>

								{!selectedTemplate.is_available && (
									<div className="p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-md text-xs text-rose-600 dark:text-rose-400 flex items-start gap-2">
										<AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
										<span>
											{selectedTemplate.unavailable_reason ||
												"This template requires an unavailable capability."}
										</span>
									</div>
								)}

								<div className="space-y-3">
									<div className="space-y-1.5">
										<Label htmlFor="alert-name" className="text-xs">
											Alert Name <span className="text-destructive">*</span>
										</Label>
										<Input
											id="alert-name"
											value={ruleName}
											onChange={(e) => setRuleName(e.target.value)}
											placeholder="e.g. Vinamilk Drop Alert"
											className="h-8 text-xs"
											data-testid="input-alert-name"
										/>
									</div>

									{selectedTemplate.parameters.map((param) => (
										<div key={param.name} className="space-y-1.5">
											<Label
												htmlFor={`param-${param.name}`}
												className="text-xs flex items-center justify-between"
											>
												<span>
													{param.label}{" "}
													{param.required && <span className="text-destructive">*</span>}
												</span>
											</Label>

											{param.type === "select" && param.options ? (
												<Select
													value={String(parameters[param.name] ?? "")}
													onValueChange={(val) => handleParamChange(param.name, val)}
												>
													<SelectTrigger id={`param-${param.name}`} className="h-8 text-xs">
														<SelectValue placeholder="Select an option" />
													</SelectTrigger>
													<SelectContent>
														{param.options.map((opt) => (
															<SelectItem key={opt.value} value={opt.value} className="text-xs">
																{opt.label}
															</SelectItem>
														))}
													</SelectContent>
												</Select>
											) : (
												<Input
													id={`param-${param.name}`}
													type={
														param.type === "number" || param.type === "integer" ? "number" : "text"
													}
													value={String(parameters[param.name] ?? "")}
													onChange={(e) => handleParamChange(param.name, e.target.value)}
													placeholder={param.description || ""}
													className="h-8 text-xs"
													data-testid={`input-param-${param.name}`}
												/>
											)}
										</div>
									))}

									<div className="space-y-1.5 pt-1">
										<Label htmlFor="alert-schedule" className="text-xs flex items-center gap-1">
											<Clock className="h-3 w-3 text-muted-foreground" />
											Monitoring Schedule
										</Label>
										<Select
											value={schedule}
											onValueChange={(val: "daily" | "weekly" | "none") => setSchedule(val)}
										>
											<SelectTrigger id="alert-schedule" className="h-8 text-xs">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="daily" className="text-xs">
													Daily check (midnight UTC)
												</SelectItem>
												<SelectItem value="weekly" className="text-xs">
													Weekly check (Monday)
												</SelectItem>
												<SelectItem value="none" className="text-xs">
													Manual run only
												</SelectItem>
											</SelectContent>
										</Select>
									</div>
								</div>
							</div>
						)}
					</div>
				)}

				<DialogFooter className="border-t pt-4">
					<Button
						variant="outline"
						size="sm"
						onClick={() => onOpenChange(false)}
						disabled={submitting}
					>
						Cancel
					</Button>
					<Button
						size="sm"
						onClick={handleCreate}
						disabled={submitting || !selectedTemplate || !selectedTemplate.is_available}
						data-testid="btn-create-alert-from-template"
					>
						{submitting ? "Creating..." : "Create Alert"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
