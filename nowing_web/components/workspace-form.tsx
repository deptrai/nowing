"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MoveLeftIcon, Plus, Search, Trash2 } from "lucide-react";
import { motion, type Variants } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
	AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Spotlight } from "@/components/ui/spotlight";
import { Tilt } from "@/components/ui/tilt";
import { cn } from "@/lib/utils";

// Define the form schema with Zod
const workspaceFormSchema = z.object({
	name: z.string().min(1, "Name is required"),
	description: z.string().optional(),
});

// Define the type for the form values
type WorkspaceFormValues = z.infer<typeof workspaceFormSchema>;

interface WorkspaceFormProps {
	onSubmit?: (data: { name: string; description?: string }) => void;
	onDelete?: () => void;
	className?: string;
	isEditing?: boolean;
	initialData?: { name: string; description?: string };
}

export function WorkspaceForm({
	onSubmit,
	onDelete,
	className,
	isEditing = false,
	initialData = { name: "", description: "" },
}: WorkspaceFormProps) {
	const [showDeleteDialog, setShowDeleteDialog] = useState(false);
	const router = useRouter();
	const t = useTranslations("common");

	// Initialize the form with React Hook Form and Zod validation
	const form = useForm<WorkspaceFormValues>({
		resolver: zodResolver(workspaceFormSchema),
		defaultValues: {
			name: initialData.name,
			description: initialData.description,
		},
	});

	// Handle form submission
	const handleFormSubmit = (values: WorkspaceFormValues) => {
		if (onSubmit) {
			onSubmit(values);
		}
	};

	// Handle delete confirmation
	const handleDelete = () => {
		if (onDelete) {
			onDelete();
		}
		setShowDeleteDialog(false);
	};

	// Animation variants
	const containerVariants = {
		hidden: { opacity: 0 },
		visible: {
			opacity: 1,
			transition: {
				staggerChildren: 0.1,
			},
		},
	};

	const itemVariants: Variants = {
		hidden: { y: 20, opacity: 0 },
		visible: {
			y: 0,
			opacity: 1,
			transition: {
				type: "spring",
				stiffness: 300,
				damping: 24,
			},
		},
	};

	return (
		<motion.div
			className={cn("space-y-8", className)}
			initial="hidden"
			animate="visible"
			variants={containerVariants}
		>
			<motion.div className="flex items-center justify-between" variants={itemVariants}>
				<div className="flex flex-col space-y-2">
					<h2 className="text-2xl md:text-3xl font-bold tracking-tight">
						{isEditing ? t("workspace_edit_title") : t("workspace_create_title")}
					</h2>
				</div>
				<Button
					variant="ghost"
					className="group relative rounded-full p-3 bg-background/80 hover:bg-muted border border-border hover:border-primary/20 shadow-sm hover:shadow-md transition-all duration-200 backdrop-blur-sm"
					onClick={() => {
						router.push("/dashboard");
					}}
				>
					<MoveLeftIcon
						size={18}
						className="text-muted-foreground group-hover:text-accent-foreground transition-colors duration-200"
					/>
					<div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/10 to-purple-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
				</Button>
			</motion.div>

			<motion.div className="w-full" variants={itemVariants}>
				<Tilt
					rotationFactor={6}
					isRevese
					springOptions={{
						stiffness: 26.7,
						damping: 4.1,
						mass: 0.2,
					}}
					className="group relative rounded-lg"
				>
					<Spotlight
						className="z-10 from-blue-500/20 via-blue-300/10 to-blue-200/5 blur-2xl"
						size={300}
						springOptions={{
							stiffness: 26.7,
							damping: 4.1,
							mass: 0.2,
						}}
					/>
					<div className="flex flex-col p-4 md:p-6 lg:p-8 rounded-xl border-2 bg-muted/30 backdrop-blur-sm transition-all hover:border-primary/50 shadow-sm">
						<div className="flex items-center justify-between mb-4">
							<div className="flex items-center space-x-4">
								<span className="p-3 rounded-full bg-blue-100 dark:bg-blue-950/50">
									<Search className="size-6 text-blue-500" aria-hidden="true" />
								</span>
								<h3 className="text-xl font-semibold">{t("workspace_label")}</h3>
							</div>
							{isEditing && onDelete && (
								<AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
									<AlertDialogTrigger asChild>
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8 rounded-full hover:bg-destructive/90 hover:text-destructive-foreground"
										>
											<Trash2 className="h-4 w-4" aria-hidden="true" />
										</Button>
									</AlertDialogTrigger>
									<AlertDialogContent>
										<AlertDialogHeader>
											<AlertDialogTitle>{t("workspace_are_you_sure")}</AlertDialogTitle>
											<AlertDialogDescription>
												{t("workspace_delete_desc")}
											</AlertDialogDescription>
										</AlertDialogHeader>
										<AlertDialogFooter>
											<AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
											<AlertDialogAction onClick={handleDelete}>{t("delete")}</AlertDialogAction>
										</AlertDialogFooter>
									</AlertDialogContent>
								</AlertDialog>
							)}
						</div>
						<p className="text-muted-foreground">
							{t("workspace_info_desc")}
						</p>
					</div>
				</Tilt>
			</motion.div>

			<Separator className="my-4" />

			<Form {...form}>
				<form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6">
					<FormField
						control={form.control}
						name="name"
						render={({ field }) => (
							<FormItem>
								<FormLabel>{t("workspace_name_label")}</FormLabel>
								<FormControl>
									<Input placeholder={t("workspace_name_placeholder")} {...field} />
								</FormControl>
								<FormDescription>{t("workspace_name_desc")}</FormDescription>
								<FormMessage />
							</FormItem>
						)}
					/>

					<FormField
						control={form.control}
						name="description"
						render={({ field }) => (
							<FormItem>
								<FormLabel>
									{t("workspace_desc_label")} <span className="text-muted-foreground font-normal">{t("workspace_desc_optional")}</span>
								</FormLabel>
								<FormControl>
									<Input placeholder={t("workspace_desc_placeholder")} {...field} />
								</FormControl>
								<FormDescription>
									{t("workspace_desc_desc")}
								</FormDescription>
								<FormMessage />
							</FormItem>
						)}
					/>

					<div className="flex justify-end pt-2">
						<Button type="submit" className="w-full sm:w-auto">
							<Plus className="mr-2 h-4 w-4" aria-hidden="true" />
							{isEditing ? t("workspace_update_btn") : t("workspace_create_btn")}
						</Button>
					</div>
				</form>
			</Form>
		</motion.div>
	);
}

export default WorkspaceForm;
