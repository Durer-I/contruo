export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    total: number;
    page: number;
    per_page: number;
  };
}
