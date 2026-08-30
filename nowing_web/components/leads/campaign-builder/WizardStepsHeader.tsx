"use client";

import { ArrowRight, Target } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface WizardStepsHeaderProps {
	currentStep: 1 | 2 | 3;
	onStepChange: (step: 1 | 2 | 3) => void;
}

export function WizardStepsHeader({ currentStep, onStepChange }: WizardStepsHeaderProps) {
	const steps = [
		{ id: 1 as const, label: "ICP Builder" },
		{ id: 2 as const, label: "Nguồn & Ngân sách" },
		{ id: 3 as const, label: "Launch & Lên lịch" },
	];

	return (
		<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-zinc-900/70 border border-zinc-800 shadow-xl backdrop-blur-md">
			<div>
				<div className="flex items-center gap-2 mb-1">
					<span className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
						<Target className="w-5 h-5" />
					</span>
					<h1 className="text-xl font-bold text-zinc-100">Campaign Builder Wizard</h1>
					<Badge
						variant="outline"
						className="bg-emerald-950/40 text-emerald-400 border-emerald-800/60 font-mono text-xs"
					>
						Story 21.15
					</Badge>
				</div>
				<p className="text-xs text-zinc-400">
					Thiết lập tiêu chí ICP, phân bổ nguồn dữ liệu đa kênh & kích hoạt SDR Pipeline tự động
				</p>
			</div>

			<div className="flex items-center gap-2">
				{steps.map((step, index) => (
					<div key={step.id} className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => onStepChange(step.id)}
							className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
								currentStep === step.id
									? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
									: "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
							}`}
						>
							<span className="w-4 h-4 rounded-full bg-black/20 flex items-center justify-center text-[10px]">
								{step.id}
							</span>
							<span>{step.label}</span>
						</button>
						{index < steps.length - 1 && <ArrowRight className="w-3 h-3 text-zinc-600" />}
					</div>
				))}
			</div>
		</div>
	);
}
