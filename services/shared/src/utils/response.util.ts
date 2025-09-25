export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  errors?: string[];
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
  timestamp: string;
}

export interface PaginationOptions {
  page: number;
  limit: number;
  total: number;
}

export class ResponseUtil {
  /**
   * Create successful response
   */
  static success<T>(
    data: T,
    message = 'Operation successful',
    pagination?: PaginationOptions
  ): ApiResponse<T> {
    const response: ApiResponse<T> = {
      success: true,
      message,
      data,
      timestamp: new Date().toISOString(),
    };

    if (pagination) {
      response.pagination = {
        page: pagination.page,
        limit: pagination.limit,
        total: pagination.total,
        totalPages: Math.ceil(pagination.total / pagination.limit),
      };
    }

    return response;
  }

  /**
   * Create error response
   */
  static error(
    message: string,
    errors: string[] = [],
    statusCode?: number
  ): ApiResponse {
    return {
      success: false,
      message,
      errors: errors.length > 0 ? errors : undefined,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Create validation error response
   */
  static validationError(errors: string[]): ApiResponse {
    return {
      success: false,
      message: 'Validation failed',
      errors,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Create not found response
   */
  static notFound(resource = 'Resource'): ApiResponse {
    return {
      success: false,
      message: `${resource} not found`,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Create unauthorized response
   */
  static unauthorized(message = 'Unauthorized access'): ApiResponse {
    return {
      success: false,
      message,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Create forbidden response
   */
  static forbidden(message = 'Access forbidden'): ApiResponse {
    return {
      success: false,
      message,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Create paginated response
   */
  static paginated<T>(
    data: T[],
    pagination: PaginationOptions,
    message = 'Data retrieved successfully'
  ): ApiResponse<T[]> {
    return this.success(data, message, pagination);
  }

  /**
   * Calculate pagination info
   */
  static calculatePagination(
    page: number = 1,
    limit: number = 10,
    total: number
  ): PaginationOptions {
    const normalizedPage = Math.max(1, page);
    const normalizedLimit = Math.max(1, Math.min(100, limit)); // Max 100 items per page

    return {
      page: normalizedPage,
      limit: normalizedLimit,
      total,
    };
  }

  /**
   * Calculate offset for database queries
   */
  static calculateOffset(page: number, limit: number): number {
    return (Math.max(1, page) - 1) * Math.max(1, limit);
  }
}