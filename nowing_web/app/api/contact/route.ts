import { type NextRequest, NextResponse } from "next/server";
import { getTranslations } from "next-intl/server";
import { z } from "zod";
import { db } from "@/app/db";
import { usersTable } from "@/app/db/schema";

// Define validation schema matching the database schema
const contactSchema = z.object({
	name: z.string().min(1, "Name is required").max(255, "Name is too long"),
	email: z.email("Invalid email address").max(255, "Email is too long"),
	company: z.string().min(1, "Company is required").max(255, "Company name is too long"),
	message: z.string().optional().prefault(""),
});

export async function POST(request: NextRequest) {
	const t = await getTranslations("api");

	try {
		const body = await request.json();

		// Validate the request body
		const validatedData = contactSchema.parse(body);

		// Insert into database
		const result = await db
			.insert(usersTable)
			.values({
				name: validatedData.name,
				email: validatedData.email,
				company: validatedData.company,
				message: validatedData.message,
			})
			.returning();

		return NextResponse.json(
			{
				success: true,
				message: t("contact_success"),
				data: result[0],
			},
			{ status: 201 }
		);
	} catch (error) {
		if (error instanceof z.ZodError) {
			return NextResponse.json(
				{
					success: false,
					message: t("validation_error"),
					errors: error.issues,
				},
				{ status: 400 }
			);
		}

		console.error("Error submitting contact form:", error);
		return NextResponse.json(
			{
				success: false,
				message: t("contact_failed"),
			},
			{ status: 500 }
		);
	}
}
