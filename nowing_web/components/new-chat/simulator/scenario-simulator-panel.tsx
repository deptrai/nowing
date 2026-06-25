"use client";

import { ChevronDownIcon, ChevronUpIcon, RefreshCwIcon } from "lucide-react";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export type ScenarioType = "base" | "bull" | "bear" | "stress";

export interface ScenarioAssumptions {
	btc_shock?: number; // -0.5 to 1.0
	eth_shock?: number;
	fee_switch_passes?: boolean;
	regulatory_adverse?: boolean;
	competitor_growth?: number; // -0.5 to 1.0
	tvl_shock?: number;
}

export interface ScenarioResult {
	scenario: ScenarioType;
	assumptions: ScenarioAssumptions;
	content: string;
	loadedAt: number;
}

interface ScenarioSimulatorPanelProps {
	threadId: number;
	tokenName?: string;
	activeScenario: ScenarioType;
	scenarioResult: ScenarioResult | null;
	isResynthesizing: boolean;
	onResynthesize: (scenario: ScenarioType, assumptions: ScenarioAssumptions) => void;
	onResetToBase: () => void;
	// Controlled state — lifted to parent so dual-DOM instances stay in sync
	selectedScenario: ScenarioType;
	assumptions: ScenarioAssumptions;
	assumptionsChanged: boolean;
	onScenarioSelect: (s: ScenarioType) => void;
	onAssumptionChange: (key: keyof ScenarioAssumptions, value: number | boolean) => void;
	className?: string;
}

const SCENARIOS: { id: ScenarioType; label: string; emoji: string }[] = [
	{ id: "base", label: "Base Case", emoji: "📊" },
	{ id: "bull", label: "Bull", emoji: "🚀" },
	{ id: "bear", label: "Bear", emoji: "🐻" },
	{ id: "stress", label: "Stress Test", emoji: "⚠️" },
];

const DEFAULT_ASSUMPTIONS: Record<ScenarioType, ScenarioAssumptions> = {
	base: {},
	bull: { btc_shock: 0.5, eth_shock: 0.4, competitor_growth: -0.2 },
	bear: { btc_shock: -0.4, eth_shock: -0.35, regulatory_adverse: true },
	stress: {
		btc_shock: -0.5,
		eth_shock: -0.5,
		tvl_shock: -0.5,
		regulatory_adverse: true,
		competitor_growth: 0.5,
	},
};

function pct(val: number): string {
	return `${val >= 0 ? "+" : ""}${(val * 100).toFixed(0)}%`;
}

export function ScenarioSimulatorPanel({
	threadId: _threadId,
	tokenName,
	activeScenario,
	scenarioResult,
	isResynthesizing,
	onResynthesize,
	onResetToBase,
	selectedScenario,
	assumptions,
	assumptionsChanged,
	onScenarioSelect,
	onAssumptionChange,
	className,
}: ScenarioSimulatorPanelProps) {
	const [collapsed, setCollapsed] = useState(false);

	const handleResynthesize = useCallback(() => {
		onResynthesize(selectedScenario, assumptions);
	}, [selectedScenario, assumptions, onResynthesize]);

	const isBaseCurrent = activeScenario === "base" && !scenarioResult;
	const canResynthesize = selectedScenario !== "base" || assumptionsChanged;

	return (
		<div
			className={cn(
				"flex w-[300px] flex-col rounded-2xl border bg-background shadow-lg",
				className
			)}
			data-slot="scenario-simulator-panel"
		>
			{/* Header */}
			<div className="flex items-center justify-between px-4 py-3 border-b">
				<div className="flex items-center gap-2">
					<span className="text-sm font-semibold">Scenario Simulator</span>
					{tokenName && <span className="text-xs text-muted-foreground">— {tokenName}</span>}
				</div>
				<button
					onClick={() => setCollapsed((c) => !c)}
					className="rounded p-1 hover:bg-muted"
					aria-label={collapsed ? "Expand" : "Collapse"}
				>
					{collapsed ? (
						<ChevronDownIcon className="size-4" />
					) : (
						<ChevronUpIcon className="size-4" />
					)}
				</button>
			</div>

			{!collapsed && (
				<div className="flex flex-col gap-4 p-4">
					{/* Scenario tabs */}
					<div className="grid grid-cols-4 gap-1 rounded-lg bg-muted p-1">
						{SCENARIOS.map((s) => (
							<button
								key={s.id}
								onClick={() => onScenarioSelect(s.id)}
								className={cn(
									"flex flex-col items-center gap-0.5 rounded-md px-1 py-1.5 text-center transition-colors",
									selectedScenario === s.id ? "bg-background shadow-sm" : "hover:bg-background/50"
								)}
							>
								<span className="text-base leading-none">{s.emoji}</span>
								<span className="text-[10px] font-medium leading-tight">{s.label}</span>
							</button>
						))}
					</div>

					{/* Assumption inputs */}
					{selectedScenario !== "base" && (
						<div className="flex flex-col gap-3">
							<AssumptionSlider
								label="BTC Price Shock"
								value={assumptions.btc_shock ?? 0}
								min={-0.5}
								max={1.0}
								step={0.05}
								format={pct}
								onChange={(v) => onAssumptionChange("btc_shock", v)}
							/>
							<AssumptionSlider
								label="ETH Price Shock"
								value={assumptions.eth_shock ?? 0}
								min={-0.5}
								max={1.0}
								step={0.05}
								format={pct}
								onChange={(v) => onAssumptionChange("eth_shock", v)}
							/>
							<AssumptionSlider
								label="Competitor Growth"
								value={assumptions.competitor_growth ?? 0}
								min={-0.5}
								max={1.0}
								step={0.05}
								format={pct}
								onChange={(v) => onAssumptionChange("competitor_growth", v)}
							/>
							<AssumptionSlider
								label="TVL Shock"
								value={assumptions.tvl_shock ?? 0}
								min={-0.5}
								max={1.0}
								step={0.05}
								format={pct}
								onChange={(v) => onAssumptionChange("tvl_shock", v)}
							/>
							<AssumptionToggle
								label="Fee Switch Passes"
								value={assumptions.fee_switch_passes ?? false}
								onChange={(v) => onAssumptionChange("fee_switch_passes", v)}
							/>
							<AssumptionToggle
								label="Regulatory Adverse"
								value={assumptions.regulatory_adverse ?? false}
								onChange={(v) => onAssumptionChange("regulatory_adverse", v)}
							/>
						</div>
					)}

					{/* Active scenario indicator */}
					{!isBaseCurrent && activeScenario !== "base" && (
						<div className="flex items-center justify-between rounded-lg bg-primary/10 px-3 py-2">
							<span className="text-xs font-medium text-primary">
								Viewing: {SCENARIOS.find((s) => s.id === activeScenario)?.emoji}{" "}
								{SCENARIOS.find((s) => s.id === activeScenario)?.label}
							</span>
							<button
								onClick={onResetToBase}
								className="text-xs text-muted-foreground hover:text-foreground underline"
							>
								View Base
							</button>
						</div>
					)}

					<Button
						size="sm"
						onClick={handleResynthesize}
						disabled={!canResynthesize || isResynthesizing}
						className="w-full gap-2"
					>
						<RefreshCwIcon className={cn("size-3.5", isResynthesizing && "animate-spin")} />
						{isResynthesizing ? "Re-synthesizing…" : "Re-synthesize"}
					</Button>
				</div>
			)}
		</div>
	);
}

function AssumptionSlider({
	label,
	value,
	min,
	max,
	step,
	format,
	onChange,
}: {
	label: string;
	value: number;
	min: number;
	max: number;
	step: number;
	format: (v: number) => string;
	onChange: (v: number) => void;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<div className="flex items-center justify-between">
				<label className="text-xs text-muted-foreground">{label}</label>
				<span
					className={cn(
						"text-xs font-mono font-medium",
						value > 0 ? "text-green-600 dark:text-green-400" : value < 0 ? "text-red-500" : ""
					)}
				>
					{format(value)}
				</span>
			</div>
			<Slider
				min={min}
				max={max}
				step={step}
				value={[value]}
				onValueChange={(values) => {
					const v = values[0];
					if (typeof v === "number" && Number.isFinite(v)) onChange(v);
				}}
				className="w-full"
			/>
		</div>
	);
}

function AssumptionToggle({
	label,
	value,
	onChange,
}: {
	label: string;
	value: boolean;
	onChange: (v: boolean) => void;
}) {
	return (
		<div className="flex items-center justify-between">
			<span className="text-xs text-muted-foreground">{label}</span>
			<button
				role="switch"
				aria-checked={value}
				onClick={() => onChange(!value)}
				className={cn(
					"relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
					value ? "bg-primary" : "bg-muted-foreground/30"
				)}
			>
				<span
					className={cn(
						"inline-block size-3.5 rounded-full bg-white shadow transition-transform",
						value ? "translate-x-4" : "translate-x-1"
					)}
				/>
			</button>
		</div>
	);
}
