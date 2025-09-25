import { ValidationError } from 'class-validator';

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

export class ValidationUtil {
  /**
   * Convert class-validator errors to readable error messages
   */
  static formatValidationErrors(errors: ValidationError[]): string[] {
    const formattedErrors: string[] = [];

    const extractErrors = (error: ValidationError, parentProperty = '') => {
      const property = parentProperty ? `${parentProperty}.${error.property}` : error.property;

      if (error.constraints) {
        Object.values(error.constraints).forEach(constraint => {
          formattedErrors.push(`${property}: ${constraint}`);
        });
      }

      if (error.children && error.children.length > 0) {
        error.children.forEach(child => extractErrors(child, property));
      }
    };

    errors.forEach(error => extractErrors(error));
    return formattedErrors;
  }

  /**
   * Check if email is valid
   */
  static isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  /**
   * Check if password meets requirements
   */
  static isValidPassword(password: string): ValidationResult {
    const errors: string[] = [];

    if (password.length < 6) {
      errors.push('Password must be at least 6 characters long');
    }

    if (password.length > 128) {
      errors.push('Password must be less than 128 characters');
    }

    if (!/[a-z]/.test(password)) {
      errors.push('Password must contain at least one lowercase letter');
    }

    if (!/[A-Z]/.test(password)) {
      errors.push('Password must contain at least one uppercase letter');
    }

    if (!/\d/.test(password)) {
      errors.push('Password must contain at least one number');
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }

  /**
   * Validate device ID format
   */
  static isValidDeviceId(deviceId: string): boolean {
    // Device ID should be alphanumeric with hyphens/underscores, 3-50 characters
    const deviceIdRegex = /^[a-zA-Z0-9_-]{3,50}$/;
    return deviceIdRegex.test(deviceId);
  }

  /**
   * Validate file name
   */
  static isValidFileName(fileName: string): boolean {
    // File name should not contain invalid characters
    const invalidChars = /[<>:"/\\|?*\x00-\x1f]/;
    return !invalidChars.test(fileName) && fileName.length > 0 && fileName.length <= 255;
  }

  /**
   * Validate coordinates
   */
  static isValidLatitude(lat: number): boolean {
    return lat >= -90 && lat <= 90;
  }

  static isValidLongitude(lng: number): boolean {
    return lng >= -180 && lng <= 180;
  }

  /**
   * Validate confidence score
   */
  static isValidConfidence(confidence: number): boolean {
    return confidence >= 0 && confidence <= 1;
  }

  /**
   * Validate bounding box coordinates (normalized 0-1)
   */
  static isValidBoundingBox(x: number, y: number, width: number, height: number): ValidationResult {
    const errors: string[] = [];

    if (x < 0 || x > 1) errors.push('X coordinate must be between 0 and 1');
    if (y < 0 || y > 1) errors.push('Y coordinate must be between 0 and 1');
    if (width < 0 || width > 1) errors.push('Width must be between 0 and 1');
    if (height < 0 || height > 1) errors.push('Height must be between 0 and 1');
    if (x + width > 1) errors.push('X + width must not exceed 1');
    if (y + height > 1) errors.push('Y + height must not exceed 1');

    return {
      isValid: errors.length === 0,
      errors,
    };
  }

  /**
   * Sanitize string input
   */
  static sanitizeString(input: string): string {
    return input.trim().replace(/\s+/g, ' ');
  }

  /**
   * Validate and sanitize metadata object
   */
  static sanitizeMetadata(metadata: Record<string, any>): Record<string, any> {
    const sanitized: Record<string, any> = {};

    for (const [key, value] of Object.entries(metadata)) {
      if (typeof key === 'string' && key.length > 0) {
        const sanitizedKey = this.sanitizeString(key);
        if (typeof value === 'string') {
          sanitized[sanitizedKey] = this.sanitizeString(value);
        } else if (typeof value === 'number' || typeof value === 'boolean') {
          sanitized[sanitizedKey] = value;
        } else if (value !== null && value !== undefined) {
          sanitized[sanitizedKey] = value;
        }
      }
    }

    return sanitized;
  }
}