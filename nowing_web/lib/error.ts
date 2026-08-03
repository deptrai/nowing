export const NOWING_ISSUES_URL = "https://github.com/deptrai/nowing/issues";

export interface ValidationFieldError {
	loc: (string | number)[];
	msg: string;
}

export class AppError extends Error {
	status?: number;
	statusText?: string;
	code?: string;
	requestId?: string;
	reportUrl?: string;
	fields?: ValidationFieldError[];
	constructor(
		message: string,
		status?: number,
		statusText?: string,
		code?: string,
		requestId?: string,
		reportUrl?: string,
		fields?: ValidationFieldError[]
	) {
		super(message);
		this.name = this.constructor.name;
		this.status = status;
		this.statusText = statusText;
		this.code = code;
		this.requestId = requestId;
		this.reportUrl = reportUrl ?? NOWING_ISSUES_URL;
		this.fields = fields;
	}
}

export class NetworkError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText, "NETWORK_ERROR");
	}
}

export class AbortedError extends AppError {
	constructor(message = "Request was cancelled.") {
		super(message, undefined, undefined, "REQUEST_ABORTED");
	}
}

export class ValidationError extends AppError {
	constructor(
		message: string,
		status?: number,
		statusText?: string,
		fields?: ValidationFieldError[]
	) {
		super(message, status, statusText, "VALIDATION_ERROR", undefined, undefined, fields);
	}
}

export class AuthenticationError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText, "UNAUTHORIZED");
	}
}

export class AuthorizationError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText, "FORBIDDEN");
	}
}

export class NotFoundError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText, "NOT_FOUND");
	}
}
