"use client";

import { useState, type FC } from "react";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface PlaybookPreset {
	id: string;
	icon: string;
	titleKey: string;
	descKey: string;
	defaultIntent: string;
	defaultSources: string[];
	exampleProduct: string;
}

const PLAYBOOK_PRESETS: PlaybookPreset[] = [
	{
		id: "real_estate",
		icon: "🏠",
		titleKey: "playbook_preset_real_estate",
		descKey: "playbook_preset_real_estate_desc",
		defaultIntent: "buy",
		defaultSources: ["batdongsan", "chotot", "muaban_bds"],
		exampleProduct: "Nhà phố Hà Nội",
	},
	{
		id: "recruitment",
		icon: "💼",
		titleKey: "playbook_preset_recruitment",
		descKey: "playbook_preset_recruitment_desc",
		defaultIntent: "hire",
		defaultSources: ["topcv", "itviec", "vietnamworks"],
		exampleProduct: "Senior Python Developer",
	},
	{
		id: "b2b_sales",
		icon: "🚀",
		titleKey: "playbook_preset_b2b_sales",
		descKey: "playbook_preset_b2b_sales_desc",
		defaultIntent: "sell",
		defaultSources: ["masothue", "mua_sam_cong"],
		exampleProduct: "SaaS HR",
	},
	{
		id: "ecommerce",
		icon: "🛒",
		titleKey: "playbook_preset_ecommerce",
		descKey: "playbook_preset_ecommerce_desc",
		defaultIntent: "sell",
		defaultSources: ["chotot", "facebook"],
		exampleProduct: "Mỹ phẩm TP.HCM",
	},
	{
		id: "education",
		icon: "🎓",
		titleKey: "playbook_preset_education",
		descKey: "playbook_preset_education_desc",
		defaultIntent: "sell",
		defaultSources: ["topcv", "facebook", "web"],
		exampleProduct: "Tiếng Anh doanh nghiệp",
	},
];

const INTENTS = [
	{ value: "buy", label: "Buy / Mua" },
	{ value: "sell", label: "Sell / Bán" },
	{ value: "hire", label: "Hire / Tuyển" },
	{ value: "partner", label: "Partner / Hợp tác" },
	{ value: "invest", label: "Invest / Đầu tư" },
	{ value: "rent", label: "Rent / Thuê" },
	{ value: "research", label: "Research / Nghiên cứu" },
];

const CHANNELS = ["email", "phone", "zalo", "linkedin", "facebook"];

export const QuickstartPlaybookBuilder: FC = () => {
	const tChat = useTranslations("chat");
	const router = useRouter();
	const params = useParams();
	const workspaceId = params?.workspace_id as string | undefined;

	const [selectedPreset, setSelectedPreset] = useState<PlaybookPreset | null>(null);
	const [step, setStep] = useState(1);
	const [intent, setIntent] = useState("buy");
	const [location, setLocation] = useState("");
	const [product, setProduct] = useState("");
	const [selectedChannels, setSelectedChannels] = useState<string[]>(["zalo"]);

	const resetWizard = () => {
		setSelectedPreset(null);
		setStep(1);
		setIntent("buy");
		setLocation("");
		setProduct("");
		setSelectedChannels(["zalo"]);
	};

	const selectPreset = (preset: PlaybookPreset) => {
		setSelectedPreset(preset);
		setStep(1);
		setIntent(preset.defaultIntent);
		setProduct(preset.exampleProduct);
	};

	const buildPrompt = (smokeTest = false) => {
		if (!selectedPreset) return "";
		const limit = smokeTest ? "5" : "20";
		const sources = selectedPreset.defaultSources.join(", ");
		const cleanProduct = product.trim() || selectedPreset.exampleProduct;
		const cleanLoc = location.trim() || "Việt Nam";
		const channelSuffix =
			selectedChannels.length > 0 ? ` qua kênh ${selectedChannels.join(", ")}` : "";
		const query = `Tìm ${limit} leads ${cleanProduct} tại ${cleanLoc} để ${intent} từ các nguồn ${sources}${channelSuffix}`;
		return query;
	};

	const run = (smokeTest = false) => {
		const rawWorkspaceId = params?.workspace_id;
		const workspaceId = Array.isArray(rawWorkspaceId) ? rawWorkspaceId[0] : rawWorkspaceId;
		const targetWorkspace = workspaceId ? String(workspaceId) : "1";
		const query = buildPrompt(smokeTest);
		const q = encodeURIComponent(query);
		resetWizard();
		router.push(`/dashboard/${targetWorkspace}/new-chat?q=${q}`);
	};

	const toggleChannel = (channel: string) => {
		setSelectedChannels((prev) =>
			prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]
		);
	};

	return (
		<div className="space-y-3">
			<div className="text-xs text-muted-foreground">
				<strong className="text-foreground">{tChat("playbook_builder_title")}</strong> •{" "}
				{tChat("playbook_builder_subtitle")}
			</div>

			<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
				{PLAYBOOK_PRESETS.map((preset) => (
					<div
						key={preset.id}
						className="p-4 rounded-2xl border border-border/80 bg-card hover:border-border transition-all flex flex-col justify-between gap-3 shadow-2xs min-w-0 cursor-pointer"
						onClick={() => selectPreset(preset)}
						onKeyDown={(e) => {
							if (e.key === "Enter" || e.key === " ") {
								e.preventDefault();
								selectPreset(preset);
							}
						}}
						role="button"
						tabIndex={0}
					>
						<div className="space-y-2">
							<div className="w-7 h-7 rounded-xl bg-primary/10 text-primary flex items-center justify-center text-sm font-bold">
								{preset.icon}
							</div>
							<h4 className="text-xs font-bold text-foreground leading-snug">
								{tChat(preset.titleKey)}
							</h4>
							<p className="text-[11px] text-muted-foreground">{tChat(preset.descKey)}</p>
						</div>
						<span className="text-left text-xs font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current rounded px-1 -mx-1">
							{tChat("playbook_start_button")}
						</span>
					</div>
				))}
			</div>

			<Dialog open={!!selectedPreset} onOpenChange={(open) => !open && resetWizard()}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="text-sm font-semibold">
							{selectedPreset ? tChat(selectedPreset.titleKey) : ""}
						</DialogTitle>
					</DialogHeader>

					<div className="space-y-4 py-2">
						{step === 1 && (
							<div className="space-y-3">
								<Label className="text-xs font-medium">{tChat("playbook_step_intent")}</Label>
								<div className="flex flex-wrap gap-2">
									{INTENTS.map((it) => (
										<Badge
											key={it.value}
											variant={intent === it.value ? "default" : "outline"}
											className="cursor-pointer text-[11px]"
											onClick={() => setIntent(it.value)}
										>
											{it.label}
										</Badge>
									))}
								</div>
								<Button size="sm" className="w-full" onClick={() => setStep(2)}>
									{tChat("playbook_next_button")}
								</Button>
							</div>
						)}

						{step === 2 && (
							<div className="space-y-3">
								<Label className="text-xs font-medium">{tChat("playbook_step_location")}</Label>
								<Input
									value={location}
									onChange={(e) => setLocation(e.target.value)}
									placeholder={tChat("playbook_location_placeholder")}
									className="text-xs"
								/>
								<div className="flex gap-2">
									<Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(1)}>
										{tChat("playbook_back_button")}
									</Button>
									<Button size="sm" className="flex-1" onClick={() => setStep(3)}>
										{tChat("playbook_next_button")}
									</Button>
								</div>
							</div>
						)}

						{step === 3 && (
							<div className="space-y-3">
								<Label className="text-xs font-medium">{tChat("playbook_step_product")}</Label>
								<Input
									value={product}
									onChange={(e) => setProduct(e.target.value)}
									placeholder={tChat("playbook_product_placeholder")}
									className="text-xs"
								/>
								<div className="flex gap-2">
									<Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(2)}>
										{tChat("playbook_back_button")}
									</Button>
									<Button size="sm" className="flex-1" onClick={() => setStep(4)}>
										{tChat("playbook_next_button")}
									</Button>
								</div>
							</div>
						)}

						{step === 4 && (
							<div className="space-y-3">
								<Label className="text-xs font-medium">{tChat("playbook_step_channels")}</Label>
								<div className="flex flex-wrap gap-2">
									{CHANNELS.map((channel) => (
										<Badge
											key={channel}
											variant={selectedChannels.includes(channel) ? "default" : "outline"}
											className="cursor-pointer text-[11px]"
											onClick={() => toggleChannel(channel)}
										>
											{channel}
										</Badge>
									))}
								</div>
								<div className="flex gap-2">
									<Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(3)}>
										{tChat("playbook_back_button")}
									</Button>
									<Button size="sm" className="flex-1" onClick={() => setStep(5)}>
										{tChat("playbook_next_button")}
									</Button>
								</div>
							</div>
						)}

						{step === 5 && (
							<div className="space-y-3">
								<Label className="text-xs font-medium">{tChat("playbook_preview_prompt")}</Label>
								<div className="rounded-lg border border-border/60 bg-muted/50 p-3 text-xs text-foreground leading-relaxed">
									{buildPrompt(true)}
								</div>
								<div className="flex gap-2">
									<Button size="sm" variant="outline" className="flex-1" onClick={() => setStep(4)}>
										{tChat("playbook_back_button")}
									</Button>
									<Button
										size="sm"
										variant="secondary"
										className="flex-1"
										onClick={() => run(true)}
									>
										{tChat("playbook_run_smoke_test")}
									</Button>
									<Button size="sm" className="flex-1" onClick={() => run(false)}>
										{tChat("playbook_run_full")}
									</Button>
								</div>
							</div>
						)}
					</div>
				</DialogContent>
			</Dialog>
		</div>
	);
};
