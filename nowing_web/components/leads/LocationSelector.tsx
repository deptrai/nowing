"use client";

import { Check, ChevronsUpDown, MapPin, Sparkles, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import type { LocationProfile, LocationType } from "@/contracts/types/leads.types";
import {
	buildLocationSummary,
	type District,
	type Province,
	QUICK_LOCATIONS,
	searchProvinces,
	VIETNAM_PROVINCES,
} from "@/lib/geo/vietnam-divisions";
import { cn } from "@/lib/utils";

export interface LocationSelectorProps {
	value?: LocationProfile | null;
	onChange: (value: LocationProfile) => void;
	className?: string;
}

const LOCATION_TYPE_OPTIONS: Array<{ value: LocationType; label: string; description: string }> = [
	{
		value: "both",
		label: "Cả hai (Mặc định)",
		description: "Nơi cư trú & địa bàn giao dịch",
	},
	{
		value: "customer_residence",
		label: "Nơi cư trú",
		description: "Khu vực khách hàng sinh sống",
	},
	{
		value: "customer_work",
		label: "Nơi làm việc",
		description: "Trụ sở công ty hoặc nơi làm việc",
	},
	{
		value: "transaction",
		label: "Địa bàn giao dịch",
		description: "Khu vực phát sinh dự án / giao dịch",
	},
];

export function LocationSelector({ value, onChange, className }: LocationSelectorProps) {
	const [provinceOpen, setProvinceOpen] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [showAdvanced, setShowAdvanced] = useState(
		(value?.ward_names && value.ward_names.length > 0) || false
	);
	const [customWardText, setCustomWardText] = useState("");

	const selectedProvince = useMemo(() => {
		if (!value?.province_code) return null;
		return VIETNAM_PROVINCES.find((p) => p.code === value.province_code) || null;
	}, [value?.province_code]);

	const filteredProvinces = useMemo(() => {
		return searchProvinces(searchQuery);
	}, [searchQuery]);

	const availableDistricts = useMemo(() => {
		return selectedProvince?.districts || [];
	}, [selectedProvince]);

	// Handlers
	const handleSelectProvince = (prov: Province) => {
		const isSame = value?.province_code === prov.code;
		const nextProfile: LocationProfile = {
			location_type: value?.location_type || "both",
			province_code: prov.code,
			province_name: prov.name,
			district_codes: isSame ? value?.district_codes || [] : [],
			district_names: isSame ? value?.district_names || [] : [],
			ward_codes: isSame ? value?.ward_codes || [] : [],
			ward_names: isSame ? value?.ward_names || [] : [],
			location_text: isSame
				? value?.location_text || prov.name
				: buildLocationSummary(prov.code, []),
		};
		onChange(nextProfile);
		setProvinceOpen(false);
	};

	const handleToggleDistrict = (dist: District) => {
		if (!selectedProvince) return;
		const currentCodes = value?.district_codes || [];
		const isSelected = currentCodes.includes(dist.code);

		let nextCodes: string[];
		let nextNames: string[];

		if (isSelected) {
			nextCodes = currentCodes.filter((c) => c !== dist.code);
			nextNames = (value?.district_names || []).filter((n) => n !== dist.name);
		} else {
			nextCodes = [...currentCodes, dist.code];
			nextNames = [...(value?.district_names || []), dist.name];
		}

		onChange({
			location_type: value?.location_type || "both",
			province_code: selectedProvince.code,
			province_name: selectedProvince.name,
			district_codes: nextCodes,
			district_names: nextNames,
			ward_codes: value?.ward_codes || [],
			ward_names: value?.ward_names || [],
			location_text: buildLocationSummary(selectedProvince.code, nextCodes),
		});
	};

	const handleLocationTypeChange = (type: LocationType) => {
		if (!value) return;
		onChange({
			...value,
			location_type: type,
		});
	};

	const handleAddCustomWard = () => {
		if (!customWardText.trim() || !value || !selectedProvince) return;
		const nextWard = customWardText.trim();
		const currentWards = value.ward_names || [];
		if (currentWards.includes(nextWard)) {
			setCustomWardText("");
			return;
		}

		const nextWards = [...currentWards, nextWard];
		setCustomWardText("");
		onChange({
			...value,
			ward_names: nextWards,
			location_text: `${buildLocationSummary(selectedProvince.code, value.district_codes)} (${nextWards.join(", ")})`,
		});
	};

	const handleRemoveWard = (wardName: string) => {
		if (!value || !selectedProvince) return;
		const nextWards = (value.ward_names || []).filter((w) => w !== wardName);
		onChange({
			...value,
			ward_names: nextWards,
			location_text:
				nextWards.length > 0
					? `${buildLocationSummary(selectedProvince.code, value.district_codes)} (${nextWards.join(", ")})`
					: buildLocationSummary(selectedProvince.code, value.district_codes),
		});
	};

	return (
		<div
			className={cn("space-y-4 rounded-xl border p-4 bg-card", className)}
			data-testid="location-selector-root"
		>
			{/* Quick location chips */}
			<div className="space-y-1.5">
				<div className="flex items-center justify-between">
					<Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
						<Sparkles className="h-3.5 w-3.5 text-primary" />
						Địa bàn trọng điểm
					</Label>
					<span className="text-[11px] text-muted-foreground">Chọn nhanh 1-click</span>
				</div>
				<div className="flex flex-wrap gap-1.5" data-testid="quick-location-chips">
					{QUICK_LOCATIONS.map((q) => {
						const isSelected = value?.province_code === q.code;
						return (
							<Button
								key={q.code}
								type="button"
								variant={isSelected ? "default" : "outline"}
								size="sm"
								className="h-7 text-xs px-2.5 rounded-full"
								onClick={() => {
									const target = VIETNAM_PROVINCES.find((p) => p.code === q.code);
									if (target) handleSelectProvince(target);
								}}
								data-testid={`quick-chip-${q.code}`}
							>
								{q.label}
							</Button>
						);
					})}
				</div>
			</div>

			{/* Province Combobox */}
			<div className="space-y-1.5">
				<Label className="text-xs font-semibold">
					Tỉnh / Thành phố <span className="text-destructive">*</span>
				</Label>
				<Popover open={provinceOpen} onOpenChange={setProvinceOpen}>
					<PopoverTrigger asChild>
						<Button
							variant="outline"
							role="combobox"
							aria-expanded={provinceOpen}
							className="w-full justify-between h-9 text-xs font-normal"
							data-testid="province-combobox-trigger"
						>
							<div className="flex items-center gap-2 truncate">
								<MapPin className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
								{selectedProvince ? (
									<span className="font-medium text-foreground">{selectedProvince.name}</span>
								) : (
									<span className="text-muted-foreground">Chọn Tỉnh / Thành phố...</span>
								)}
							</div>
							<ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
						</Button>
					</PopoverTrigger>
					<PopoverContent className="w-[320px] p-0" align="start">
						<Command shouldFilter={false}>
							<CommandInput
								placeholder="Nhập tên tỉnh hoặc viết tắt (hn, hcm, sg)..."
								value={searchQuery}
								onValueChange={setSearchQuery}
								className="h-9 text-xs"
								data-testid="province-search-input"
							/>
							<CommandList className="max-h-60 overflow-y-auto text-xs">
								<CommandEmpty className="py-4 text-center text-xs text-muted-foreground">
									Không tìm thấy tỉnh thành nào.
								</CommandEmpty>
								<CommandGroup>
									{filteredProvinces.map((prov) => {
										const isSelected = value?.province_code === prov.code;
										return (
											<CommandItem
												key={prov.code}
												value={prov.code}
												onSelect={() => handleSelectProvince(prov)}
												className="flex items-center justify-between text-xs py-2 cursor-pointer"
												data-testid={`province-item-${prov.code}`}
											>
												<span>{prov.name}</span>
												{isSelected && <Check className="h-3.5 w-3.5 text-primary" />}
											</CommandItem>
										);
									})}
								</CommandGroup>
							</CommandList>
						</Command>
					</PopoverContent>
				</Popover>
			</div>

			{/* Location Type Selector */}
			{selectedProvince && (
				<div className="space-y-1.5 border-t pt-3">
					<Label className="text-xs font-semibold text-muted-foreground">
						Mục tiêu nhắm chọn (Location Semantics)
					</Label>
					<div className="grid grid-cols-2 gap-2" data-testid="location-type-options">
						{LOCATION_TYPE_OPTIONS.map((opt) => {
							const isChecked = (value?.location_type || "both") === opt.value;
							return (
								<button
									key={opt.value}
									type="button"
									onClick={() => handleLocationTypeChange(opt.value)}
									className={cn(
										"p-2 rounded-lg border text-left transition-all",
										isChecked
											? "border-primary bg-primary/5 shadow-xs"
											: "border-border/60 hover:border-primary/40 hover:bg-muted/40"
									)}
									data-testid={`location-type-${opt.value}`}
								>
									<p className="text-xs font-semibold leading-none">{opt.label}</p>
									<p className="text-[10px] text-muted-foreground mt-1 line-clamp-1">
										{opt.description}
									</p>
								</button>
							);
						})}
					</div>
				</div>
			)}

			{/* District multi-select (Progressive Disclosure) */}
			{selectedProvince && availableDistricts.length > 0 && (
				<div className="space-y-2 border-t pt-3" data-testid="district-selector-section">
					<div className="flex items-center justify-between">
						<Label className="text-xs font-semibold">
							Quận / Huyện thuộc {selectedProvince.name}
						</Label>
						<span className="text-[11px] text-muted-foreground">
							{value?.district_codes?.length || 0} đã chọn (để trống = toàn tỉnh)
						</span>
					</div>

					<div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 rounded-lg border bg-muted/20">
						{availableDistricts.map((dist) => {
							const isChecked = (value?.district_codes || []).includes(dist.code);
							return (
								<Badge
									key={dist.code}
									variant={isChecked ? "default" : "outline"}
									className={cn(
										"cursor-pointer text-xs font-normal transition-all select-none",
										isChecked
											? "bg-primary text-primary-foreground hover:bg-primary/90"
											: "hover:bg-muted"
									)}
									onClick={() => handleToggleDistrict(dist)}
									data-testid={`district-badge-${dist.code}`}
								>
									{dist.name}
								</Badge>
							);
						})}
					</div>
				</div>
			)}

			{/* Advanced Ward Section (Progressive Collapse) */}
			{selectedProvince && (
				<div className="space-y-3 border-t pt-3">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="advanced-toggle" className="text-xs font-semibold cursor-pointer">
								Khu vực chi tiết (nâng cao)
							</Label>
							<p className="text-[11px] text-muted-foreground">
								Thêm Phường, Xã hoặc Tuyến đường cụ thể
							</p>
						</div>
						<Switch
							id="advanced-toggle"
							checked={showAdvanced}
							onCheckedChange={setShowAdvanced}
							data-testid="advanced-ward-toggle"
						/>
					</div>

					{showAdvanced && (
						<div className="space-y-2 rounded-lg border p-3 bg-muted/10">
							<div className="flex gap-2">
								<input
									type="text"
									value={customWardText}
									onChange={(e) => setCustomWardText(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault();
											handleAddCustomWard();
										}
									}}
									placeholder="Ví dụ: Phường Bến Nghé, KĐT Ciputra..."
									className="flex-1 h-8 px-2.5 rounded-md border text-xs bg-background focus:outline-hidden focus:ring-1 focus:ring-primary"
									data-testid="input-custom-ward"
								/>
								<Button
									type="button"
									size="sm"
									className="h-8 text-xs px-3"
									onClick={handleAddCustomWard}
									data-testid="btn-add-ward"
								>
									Thêm
								</Button>
							</div>

							{value?.ward_names && value.ward_names.length > 0 && (
								<div className="flex flex-wrap gap-1.5 pt-1">
									{value.ward_names.map((ward) => (
										<Badge key={ward} variant="secondary" className="text-[11px] gap-1 px-2 py-0.5">
											<span>{ward}</span>
											<button
												type="button"
												onClick={() => handleRemoveWard(ward)}
												className="hover:text-destructive"
												data-testid={`remove-ward-${ward}`}
											>
												<X className="h-3 w-3" />
											</button>
										</Badge>
									))}
								</div>
							)}
						</div>
					)}
				</div>
			)}

			{/* Selected Location Profile Summary Card */}
			{value?.province_code && (
				<div className="rounded-lg bg-primary/5 border border-primary/20 p-2.5 flex items-center justify-between text-xs">
					<div className="flex items-center gap-2 min-w-0">
						<MapPin className="h-4 w-4 text-primary shrink-0" />
						<span className="truncate font-medium text-foreground">{value.location_text}</span>
					</div>
					<Badge variant="outline" className="text-[10px] shrink-0 uppercase border-primary/30">
						{value.location_type}
					</Badge>
				</div>
			)}
		</div>
	);
}
