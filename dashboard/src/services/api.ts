import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'

export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data?: T
  errors?: string[]
  pagination?: {
    page: number
    limit: number
    total: number
    totalPages: number
  }
  timestamp: string
}

class ApiService {
  private api: AxiosInstance

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_URL || 'http://localhost:3000/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // Request interceptor
    this.api.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('authToken')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        
        // Log requests in development
        if (import.meta.env.DEV) {
          console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
        }
        
        return config
      },
      (error) => {
        console.error('API Request Error:', error)
        return Promise.reject(error)
      }
    )

    // Response interceptor
    this.api.interceptors.response.use(
      (response: AxiosResponse<ApiResponse>) => {
        // Log responses in development
        if (import.meta.env.DEV) {
          console.log(`API Response: ${response.status} ${response.config.url}`)
        }
        
        return response
      },
      (error) => {
        console.error('API Response Error:', error)
        
        // Handle common errors
        if (error.response?.status === 401) {
          // Unauthorized - redirect to login
          localStorage.removeItem('authToken')
          window.location.href = '/login'
        } else if (error.response?.status === 403) {
          // Forbidden
          console.error('Access forbidden')
        } else if (error.response?.status >= 500) {
          // Server error
          console.error('Server error occurred')
        }
        
        return Promise.reject(error)
      }
    )
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
    return this.api.get(url, config)
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
    return this.api.post(url, data, config)
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
    return this.api.put(url, data, config)
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
    return this.api.patch(url, data, config)
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
    return this.api.delete(url, config)
  }

  // File upload method
  async uploadFile<T = any>(
    url: string,
    file: File,
    options?: {
      onUploadProgress?: (progressEvent: any) => void
      additionalData?: Record<string, any>
    }
  ): Promise<AxiosResponse<ApiResponse<T>>> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (options?.additionalData) {
      Object.entries(options.additionalData).forEach(([key, value]) => {
        formData.append(key, value)
      })
    }

    return this.api.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: options?.onUploadProgress,
    })
  }

  // Utility methods
  setAuthToken(token: string) {
    localStorage.setItem('authToken', token)
    this.api.defaults.headers.Authorization = `Bearer ${token}`
  }

  clearAuthToken() {
    localStorage.removeItem('authToken')
    delete this.api.defaults.headers.Authorization
  }

  getAuthToken(): string | null {
    return localStorage.getItem('authToken')
  }

  isAuthenticated(): boolean {
    return !!this.getAuthToken()
  }

  // Health check
  async healthCheck() {
    try {
      const response = await this.get('/health')
      return response.data
    } catch (error) {
      console.error('Health check failed:', error)
      throw error
    }
  }
}

// Create and export a singleton instance
export const apiService = new ApiService()
export default apiService