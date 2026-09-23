/**
 * Authentication error messages and handling utilities.
 *
 * Error messages are i18n keys resolved via next-intl's `t` from the "auth"
 * namespace, so callers must pass their `t` function.
 */

export interface AuthErrorMapping {
	[key: string]: {
		titleKey: string;
		descriptionKey?: string;
	};
}

const AUTH_ERROR_MESSAGES: AuthErrorMapping = {
	// Common HTTP errors
	"401": {
		titleKey: "error_invalid_credentials_title",
		descriptionKey: "error_invalid_credentials_desc",
	},
	"403": {
		titleKey: "error_access_denied_title",
		descriptionKey: "error_access_denied_desc",
	},
	"404": {
		titleKey: "error_not_found_title",
		descriptionKey: "error_not_found_desc",
	},
	"409": {
		titleKey: "error_account_conflict_title",
		descriptionKey: "error_account_conflict_desc",
	},
	"429": {
		titleKey: "error_too_many_attempts_title",
		descriptionKey: "error_too_many_attempts_desc",
	},
	RATE_LIMIT_EXCEEDED: {
		titleKey: "error_too_many_attempts_title",
		descriptionKey: "error_too_many_requests_desc",
	},
	"500": {
		titleKey: "error_server_title",
		descriptionKey: "error_server_desc",
	},
	"503": {
		titleKey: "error_unavailable_title",
		descriptionKey: "error_unavailable_desc",
	},

	// FastAPI specific errors
	LOGIN_BAD_CREDENTIALS: {
		titleKey: "error_login_failed_title",
		descriptionKey: "error_login_failed_desc",
	},
	LOGIN_USER_NOT_VERIFIED: {
		titleKey: "error_not_verified_title",
		descriptionKey: "error_not_verified_desc",
	},
	USER_INACTIVE: {
		titleKey: "error_inactive_title",
		descriptionKey: "error_inactive_desc",
	},
	REGISTER_USER_ALREADY_EXISTS: {
		titleKey: "error_already_exists_title",
		descriptionKey: "error_already_exists_desc",
	},
	REGISTER_INVALID_PASSWORD: {
		titleKey: "error_invalid_password_title",
		descriptionKey: "error_invalid_password_desc",
	},

	// OAuth errors
	access_denied: {
		titleKey: "error_oauth_denied_title",
		descriptionKey: "error_oauth_denied_desc",
	},
	invalid_request: {
		titleKey: "error_invalid_request_title",
		descriptionKey: "error_invalid_request_desc",
	},
	unauthorized_client: {
		titleKey: "error_auth_failed_title",
		descriptionKey: "error_auth_failed_desc",
	},
	unsupported_response_type: {
		titleKey: "error_method_unsupported_title",
		descriptionKey: "error_method_unsupported_desc",
	},
	invalid_scope: {
		titleKey: "error_invalid_perms_title",
		descriptionKey: "error_invalid_perms_desc",
	},
	server_error: {
		titleKey: "error_server_title",
		descriptionKey: "error_auth_server_desc",
	},
	temporarily_unavailable: {
		titleKey: "error_unavailable_title",
		descriptionKey: "error_login_unavailable_desc",
	},

	// Network errors
	NETWORK_ERROR: {
		titleKey: "error_connection_failed_title",
		descriptionKey: "error_connection_failed_desc",
	},
	TIMEOUT: {
		titleKey: "error_timeout_title",
		descriptionKey: "error_timeout_desc",
	},

	// Generic fallbacks
	UNKNOWN_ERROR: {
		titleKey: "error_generic_title",
		descriptionKey: "error_generic_desc",
	},
};

type AuthTranslator = (key: string) => string;

function resolveErrorInfo(errorCode: string): { titleKey: string; descriptionKey?: string } {
	if (!errorCode) {
		return AUTH_ERROR_MESSAGES.UNKNOWN_ERROR;
	}

	// Clean up the error code
	const cleanErrorCode = errorCode.trim().toUpperCase();

	// Try exact match first
	let errorInfo = AUTH_ERROR_MESSAGES[cleanErrorCode] || AUTH_ERROR_MESSAGES[errorCode];

	// Try partial matches for HTTP status codes
	if (!errorInfo) {
		const statusCodeMatch = errorCode.match(/(\d{3})/);
		if (statusCodeMatch) {
			errorInfo = AUTH_ERROR_MESSAGES[statusCodeMatch[1]];
		}
	}

	// Try partial matches for common error patterns
	if (!errorInfo) {
		const patterns = [
			{ pattern: /credential|password|email/i, code: "LOGIN_BAD_CREDENTIALS" },
			{ pattern: /verify|verification/i, code: "LOGIN_USER_NOT_VERIFIED" },
			{ pattern: /inactive|disabled|suspended/i, code: "USER_INACTIVE" },
			{ pattern: /exists|duplicate/i, code: "REGISTER_USER_ALREADY_EXISTS" },
			{ pattern: /network|connection/i, code: "NETWORK_ERROR" },
			{ pattern: /timeout/i, code: "TIMEOUT" },
			{ pattern: /rate|limit|many/i, code: "429" },
		];

		for (const { pattern, code } of patterns) {
			if (pattern.test(errorCode)) {
				errorInfo = AUTH_ERROR_MESSAGES[code];
				break;
			}
		}
	}

	// Fallback to unknown error
	if (!errorInfo) {
		errorInfo = AUTH_ERROR_MESSAGES.UNKNOWN_ERROR;
	}

	return errorInfo;
}

/**
 * Get a user-friendly error message for authentication errors
 * @param t - Translation function from useTranslations("auth")
 * @param errorCode - The error code or message from the API
 * @param returnTitle - Whether to return just the title or full description
 * @returns Formatted error message
 */
export function getAuthErrorMessage(
	t: AuthTranslator,
	errorCode: string,
	returnTitle: boolean = false
): string {
	const errorInfo = resolveErrorInfo(errorCode);
	return returnTitle ? t(errorInfo.titleKey) : t(errorInfo.descriptionKey || errorInfo.titleKey);
}

/**
 * Get both title and description for an error
 * @param t - Translation function from useTranslations("auth")
 * @param errorCode - The error code or message from the API
 * @returns Object with title and description
 */
export function getAuthErrorDetails(
	t: AuthTranslator,
	errorCode: string
): { title: string; description: string } {
	const title = getAuthErrorMessage(t, errorCode, true);
	const description = getAuthErrorMessage(t, errorCode, false);

	return { title, description };
}

/**
 * Check if an error is a network-related error
 * @param error - The error object or message
 * @returns True if it's a network error
 */
export function isNetworkError(error: unknown): boolean {
	if (error instanceof TypeError && error.message.includes("fetch")) {
		return true;
	}

	if (typeof error === "string") {
		return /network|connection|fetch|cors/i.test(error);
	}

	return false;
}

/**
 * Check if an error should trigger a retry action
 * @param errorCode - The error code or message
 * @returns True if retry is recommended
 */
export function shouldRetry(errorCode: string): boolean {
	const retryableCodes = [
		"500",
		"503",
		"429",
		"NETWORK_ERROR",
		"TIMEOUT",
		"server_error",
		"temporarily_unavailable",
	];

	return retryableCodes.some(
		(code) => errorCode.includes(code) || errorCode.toUpperCase().includes(code)
	);
}
