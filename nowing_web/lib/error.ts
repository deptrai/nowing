export class AppError extends Error {
	status?: number;
	statusText?: string;
	constructor(message: string, status?: number, statusText?: string) {
		super(message);
		this.name = this.constructor.name; // User friendly
		this.status = status;
		this.statusText = statusText; // Dev friendly
	}
}

export class NetworkError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText);
	}
}

export class ValidationError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText);
	}
}

export class AuthenticationError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText);
	}
}

export class AuthorizationError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText);
	}
}

export class NotFoundError extends AppError {
	constructor(message: string, status?: number, statusText?: string) {
		super(message, status, statusText);
	}
}

export class QuotaExceededError extends AppError {
	constructor(message = "Token quota exceeded") {
		super(message, 402, "Payment Required");
	}
}

export class StreamMaxRetriesError extends AppError {
	constructor(message = "Stream connection lost — max retries exceeded") {
		super(message);
	}
}
