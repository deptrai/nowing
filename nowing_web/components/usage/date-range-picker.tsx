"use client";

import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { UsageDateRange } from "@/contracts/types/usage.types";
import { cn } from "@/lib/utils";

interface UsageDateRangePickerProps {
	value: UsageDateRange;
	onChange: (range: UsageDateRange) => void;
}

const PRESETS = [7, 30, 90] as const;

type PresetDays = (typeof PRESETS)[number];

function rangeForDays(days: PresetDays): UsageDateRange {
	const now = new Date();
	const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
	return { start: start.toISOString(), end: now.toISOString() };
}

function isActivePreset(value: UsageDateRange, days: PresetDays): boolean {
	const now = Date.now();
	const expectedEnd = now;
	const expectedStart = now - days * 24 * 60 * 60 * 1000;
	const actualEnd = new Date(value.end).getTime();
	const actualStart = new Date(value.start).getTime();
	const epsilon = 60 * 1000;
	return (
		Math.abs(actualEnd - expectedEnd) < epsilon && Math.abs(actualStart - expectedStart) < epsilon
	);
}

function isoEndOfDayUtc(date: Date): string {
	const d = new Date(
		Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999)
	);
	return d.toISOString();
}

function isoStartOfDayUtc(date: Date): string {
	const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
	return d.toISOString();
}

function toUtcMidnight(date: Date): Date {
	return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
}

function formatUtcDate(date: Date): string {
	return toUtcMidnight(date).toLocaleDateString(undefined, { timeZone: "UTC" });
}

function formatRangeLabel(range: DateRange | undefined): string {
	if (!range?.from) return "Custom";
	const from = formatUtcDate(range.from);
	if (!range.to) return from;
	const to = formatUtcDate(range.to);
	return from === to ? from : `${from} - ${to}`;
}

function valueToDateRange(value: UsageDateRange): DateRange {
	return { from: new Date(value.start), to: new Date(value.end) };
}

export function UsageDateRangePicker({ value, onChange }: UsageDateRangePickerProps) {
	const [isCustomOpen, setIsCustomOpen] = useState(false);
	const [draftRange, setDraftRange] = useState<DateRange | undefined>();

	const activeDays = PRESETS.find((days) => isActivePreset(value, days)) ?? null;
	const isCustomActive = activeDays === null;

	const handleOpenChange = (open: boolean) => {
		setIsCustomOpen(open);
		if (open) {
			setDraftRange(undefined);
		}
	};

	const handleSelect = (range: DateRange | undefined) => {
		setDraftRange(range);
	};

	const handleApply = () => {
		if (draftRange?.from && draftRange?.to) {
			onChange({
				start: isoStartOfDayUtc(draftRange.from),
				end: isoEndOfDayUtc(draftRange.to),
			});
			setIsCustomOpen(false);
		}
	};

	const label = isCustomActive
		? draftRange?.from
			? formatRangeLabel(draftRange)
			: formatRangeLabel(valueToDateRange(value))
		: "Custom";

	return (
		<div className="flex flex-wrap items-center gap-2" data-testid="usage-date-range-picker">
			{PRESETS.map((days) => (
				<Button
					key={days}
					variant={activeDays === days ? "default" : "outline"}
					size="sm"
					onClick={() => onChange(rangeForDays(days))}
				>
					Last {days} days
				</Button>
			))}
			<Popover open={isCustomOpen} onOpenChange={handleOpenChange}>
				<PopoverTrigger asChild>
					<Button
						variant={isCustomActive ? "default" : "outline"}
						size="sm"
						className={cn("gap-2", isCustomActive && "max-w-[12rem] truncate")}
					>
						<CalendarIcon className="h-4 w-4" />
						{label}
					</Button>
				</PopoverTrigger>
				<PopoverContent className="w-auto p-2" align="end">
					<Calendar
						mode="range"
						selected={draftRange}
						onSelect={handleSelect}
						numberOfMonths={2}
						initialFocus
					/>
					<div className="mt-2 flex justify-end gap-2">
						<Button variant="outline" size="sm" onClick={() => setIsCustomOpen(false)}>
							Cancel
						</Button>
						<Button size="sm" disabled={!draftRange?.from || !draftRange?.to} onClick={handleApply}>
							Apply
						</Button>
					</div>
				</PopoverContent>
			</Popover>
		</div>
	);
}
