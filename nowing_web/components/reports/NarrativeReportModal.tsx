"use client";

import { Calendar, FileText, LineChart, Newspaper, Sparkles } from "lucide-react";
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
import type { NarrativeTemplate, ReportContentRead } from "@/contracts/types/reports.types";
import { reportsApiService } from "@/lib/apis/reports-api.service";

interface NarrativeReportModalProps {
	workspaceId: number;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onGenerated?: (report: ReportContentRead) => void;
}

export default function NarrativeReportModal({
	workspaceId,
	open,
	onOpenChange,
	onGenerated,
}: NarrativeReportModalProps) {
	const [templates, setTemplates] = useState<NarrativeTemplate[]>([]);
	const [loading, setLoading] = useState(false);
	const [selectedTemplate, setSelectedTemplate] = useState<NarrativeTemplate | null>(null);
	const [customTitle, setCustomTitle] = useState("");
	const [parameters, setParameters] = useState<Record<string, unknown>>({});
	const [submitting, setSubmitting] = useState(false);

	const handleSelectTemplate = useCallback((template: NarrativeTemplate) => {
		setSelectedTemplate(template);
		setCustomTitle(template.name);
		const defaults: Record<string, unknown> = {};
		for (const p of template.parameters) {
			defaults[p.name] = p.default !== undefined ? p.default : "";
		}
		setParameters(defaults);
	}, []);

	useEffect(() => {
		if (open) {
			setLoading(true);
			reportsApiService
				.listNarrativeTemplates(workspaceId)
				.then((items) => {
					setTemplates(items);
					if (items.length > 0 && !selectedTemplate) {
						handleSelectTemplate(items[0]);
					}
				})
				.catch((err) => {
					console.error("Failed to fetch narrative templates:", err);
					toast.error("Could not load narrative templates");
				})
				.finally(() => setLoading(false));
		}
	}, [open, workspaceId, handleSelectTemplate, selectedTemplate]);

	const handleParamChange = (name: string, value: unknown) => {
		setParameters((prev) => ({ ...prev, [name]: value }));
	};

	const handleGenerate = async () => {
		if (!selectedTemplate) return;

		setSubmitting(true);
		try {
			const report = await reportsApiService.generateNarrativeReport(workspaceId, {
				template_id: selectedTemplate.template_id,
				title: customTitle.trim() || undefined,
				parameters,
			});
			toast.success(`Narrative report "${report.title}" generated successfully!`);
			onGenerated?.(report);
			onOpenChange(false);
		} catch (err: unknown) {
			console.error("Failed to generate narrative report:", err);
			const errorMsg =
				err && typeof err === "object" && "message" in err
					? String((err as { message: unknown }).message)
					: "Could not generate narrative report";
			toast.error(errorMsg);
		} finally {
			setSubmitting(false);
		}
	};

	const getStyleIcon = (style: string) => {
		switch (style) {
			case "digest":
				return <Newspaper className="h-4 w-4 text-sky-500" />;
			case "trend":
				return <LineChart className="h-4 w-4 text-emerald-500" />;
			case "timeline":
				return <Calendar className="h-4 w-4 text-amber-500" />;
			default:
				return <FileText className="h-4 w-4 text-primary" />;
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				className="max-w-2xl max-h-[85vh] flex flex-col p-6"
				data-testid="narrative-report-modal"
			>
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						<Sparkles className="h-5 w-5 text-primary" />
						Generate Narrative Report
					</DialogTitle>
					<DialogDescription>
						Synthesize indexed news, financial trend data, or corporate timelines into grounded
						executive reports.
					</DialogDescription>
				</DialogHeader>

				{loading ? (
					<div className="py-12 text-center text-sm text-muted-foreground animate-pulse">
						Loading narrative templates...
					</div>
				) : (
					<div className="grid grid-cols-1 md:grid-cols-5 gap-6 py-2 overflow-y-auto">
						{/* Template picker */}
						<div className="md:col-span-2 space-y-2 border-r pr-4">
							<Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
								Narrative Styles
							</Label>
							<div className="space-y-1.5">
								{templates.map((tmpl) => {
									const isSelected = selectedTemplate?.template_id === tmpl.template_id;
									return (
										<button
											key={tmpl.template_id}
											type="button"
											onClick={() => handleSelectTemplate(tmpl)}
											className={`w-full text-left p-2.5 rounded-lg border transition-all flex items-start gap-2.5 ${
												isSelected
													? "border-primary bg-primary/5 shadow-xs"
													: "border-border hover:border-primary/50 hover:bg-muted/50"
											}`}
											data-testid={`narrative-tmpl-${tmpl.template_id}`}
										>
											<div className="mt-0.5 shrink-0">{getStyleIcon(tmpl.narrative_style)}</div>
											<div className="min-w-0 flex-1">
												<div className="flex items-center justify-between gap-1">
													<p className="text-xs font-semibold truncate">{tmpl.name}</p>
													<Badge variant="outline" className="text-[9px] uppercase px-1 h-3.5">
														{tmpl.narrative_style}
													</Badge>
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

						{/* Form inputs */}
						{selectedTemplate && (
							<div className="md:col-span-3 space-y-4">
								<div className="space-y-1 border-b pb-3">
									<div className="flex items-center gap-2">
										{getStyleIcon(selectedTemplate.narrative_style)}
										<h4 className="font-semibold text-sm">{selectedTemplate.name}</h4>
									</div>
									<p className="text-xs text-muted-foreground">{selectedTemplate.description}</p>
								</div>

								<div className="space-y-3">
									<div className="space-y-1.5">
										<Label htmlFor="report-title" className="text-xs">
											Report Title
										</Label>
										<Input
											id="report-title"
											value={customTitle}
											onChange={(e) => setCustomTitle(e.target.value)}
											placeholder="Custom title or leave default"
											className="h-8 text-xs"
										/>
									</div>

									{selectedTemplate.parameters.map((param) => (
										<div key={param.name} className="space-y-1.5">
											<Label htmlFor={`param-${param.name}`} className="text-xs">
												{param.label}{" "}
												{param.required && <span className="text-destructive">*</span>}
											</Label>
											<Input
												id={`param-${param.name}`}
												type={
													param.type === "integer" || param.type === "number" ? "number" : "text"
												}
												value={String(parameters[param.name] ?? "")}
												onChange={(e) => handleParamChange(param.name, e.target.value)}
												placeholder={param.description || ""}
												className="h-8 text-xs"
												data-testid={`input-narrative-${param.name}`}
											/>
										</div>
									))}
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
						onClick={handleGenerate}
						disabled={submitting || !selectedTemplate}
						data-testid="btn-generate-narrative-submit"
						className="gap-1.5"
					>
						<Sparkles className="h-3.5 w-3.5" />
						{submitting ? "Synthesizing..." : "Generate Report"}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
