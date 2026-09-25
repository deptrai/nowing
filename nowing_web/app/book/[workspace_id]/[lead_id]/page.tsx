"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle, CalendarCheck, CheckCircle2, Video } from "lucide-react";
import { motion } from "motion/react";
import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { buildBackendUrl } from "@/lib/env-config";

// Story 37.3: prospect-facing booking page. Public by design - the lead UUID
// in the URL is the capability, backed by /api/v1/public/book/* endpoints.

interface MeetingSlot {
	start: string;
	end: string;
	label: string;
}

interface SlotsResponse {
	slots: MeetingSlot[];
	provider: string | null;
}

interface BookResponse {
	booked: boolean;
	meeting_link: string | null;
}

export default function MeetingBookingPage() {
	const params = useParams();
	const workspaceId = params.workspace_id as string;
	const leadId = params.lead_id as string;

	const [selected, setSelected] = useState<MeetingSlot | null>(null);
	const [email, setEmail] = useState("");
	const [booking, setBooking] = useState(false);
	const [booked, setBooked] = useState<BookResponse | null>(null);
	const [error, setError] = useState<string | null>(null);

	const { data, isLoading, isError, refetch } = useQuery({
		queryKey: ["public-meeting-slots", workspaceId, leadId],
		queryFn: async (): Promise<SlotsResponse> => {
			const res = await fetch(
				buildBackendUrl(`/api/v1/public/book/${workspaceId}/${leadId}/slots`)
			);
			if (res.status === 404) throw new Error("invalid_link");
			if (!res.ok) throw new Error("fetch_failed");
			return res.json();
		},
		retry: false,
		staleTime: 30_000,
	});

	const handleBook = async () => {
		if (!selected) return;
		setBooking(true);
		setError(null);
		try {
			const res = await fetch(
				buildBackendUrl(`/api/v1/public/book/${workspaceId}/${leadId}/book`),
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						start: selected.start,
						duration_minutes: 30,
						attendee_email: email.trim() || null,
					}),
				}
			);
			if (res.status === 409) {
				setError("Khung giờ này vừa được đặt. Vui lòng chọn giờ khác.");
				setSelected(null);
				refetch();
				return;
			}
			if (res.status === 404) throw new Error("invalid_link");
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				throw new Error(typeof body.detail === "string" ? body.detail : "Đặt lịch thất bại");
			}
			setBooked(await res.json());
		} catch (err) {
			setError(
				err instanceof Error && err.message === "invalid_link"
					? "Liên kết đặt lịch không hợp lệ."
					: "Không đặt được lịch. Vui lòng thử lại sau."
			);
		} finally {
			setBooking(false);
		}
	};

	const invalidLink = isError || (data !== undefined && !isError && data.slots === undefined);

	return (
		<div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-background to-primary/5">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.4, ease: "easeOut" }}
				className="w-full max-w-md"
			>
				<Card className="border-none shadow-2xl bg-card/80 backdrop-blur-xl">
					{isLoading ? (
						<CardContent className="flex flex-col items-center justify-center py-16">
							<Spinner size="xl" className="text-primary" />
							<p className="mt-4 text-muted-foreground">Đang tải lịch trống…</p>
						</CardContent>
					) : invalidLink ? (
						<CardContent className="flex flex-col items-center justify-center py-16 text-center">
							<AlertCircle className="h-10 w-10 text-destructive mb-4" />
							<p className="font-medium">Liên kết đặt lịch không hợp lệ</p>
							<p className="text-sm text-muted-foreground mt-2">
								Vui lòng liên hệ lại người tư vấn để nhận liên kết mới.
							</p>
						</CardContent>
					) : booked ? (
						<>
							<CardHeader className="text-center pb-4">
								<motion.div
									initial={{ scale: 0 }}
									animate={{ scale: 1 }}
									transition={{ type: "spring", stiffness: 200, damping: 15 }}
									className="mx-auto mb-4 h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-emerald-500/5 flex items-center justify-center ring-4 ring-emerald-500/20"
								>
									<CheckCircle2 className="h-10 w-10 text-emerald-500" />
								</motion.div>
								<CardTitle className="text-2xl">Đặt lịch thành công</CardTitle>
								<CardDescription>
									{selected?.label} — lời mời đã được gửi qua email
									{email.trim() ? ` ${email.trim()}` : ""}.
								</CardDescription>
							</CardHeader>
							{booked.meeting_link && (
								<CardContent>
									<a
										href={booked.meeting_link}
										target="_blank"
										rel="noreferrer"
										className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
									>
										<Video className="h-5 w-5 text-primary shrink-0" />
										<span className="text-sm truncate">{booked.meeting_link}</span>
									</a>
								</CardContent>
							)}
						</>
					) : (
						<>
							<CardHeader className="text-center pb-4">
								<div className="mx-auto mb-4 h-16 w-16 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center ring-4 ring-primary/20">
									<CalendarCheck className="h-8 w-8 text-primary" />
								</div>
								<CardTitle className="text-2xl">Chọn thời gian hẹn</CardTitle>
								<CardDescription>Cuộc hẹn 30 phút, giờ Việt Nam (GMT+7)</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								{data && data.slots.length === 0 ? (
									<p className="text-center text-sm text-muted-foreground py-6">
										Hiện chưa có khung giờ trống. Vui lòng liên hệ lại người tư vấn.
									</p>
								) : (
									<div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
										{data?.slots.map((slot) => (
											<Button
												key={slot.start}
												variant={selected?.start === slot.start ? "default" : "outline"}
												className="w-full"
												onClick={() => setSelected(slot)}
											>
												{slot.label}
											</Button>
										))}
									</div>
								)}
								<Input
									type="email"
									placeholder="Email nhận lời mời (không bắt buộc)"
									value={email}
									onChange={(e) => setEmail(e.target.value)}
								/>
								{error && (
									<div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg text-sm">
										<AlertCircle className="h-4 w-4 shrink-0" />
										{error}
									</div>
								)}
							</CardContent>
							<CardFooter>
								<Button
									className="w-full"
									disabled={!selected || booking || !data?.slots.length}
									onClick={handleBook}
								>
									{booking ? <Spinner size="sm" /> : "Xác nhận đặt lịch"}
								</Button>
							</CardFooter>
						</>
					)}
				</Card>
				<div className="mt-6 text-center">
					<Link
						href="/"
						className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
					>
						<Image src="/icon-128.svg" alt="Nowing" width={24} height={24} className="rounded" />
						<span className="text-sm font-medium">Nowing</span>
					</Link>
				</div>
			</motion.div>
		</div>
	);
}
