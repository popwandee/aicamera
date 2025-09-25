// Re-export shared types from the backend
export type {
  IEdgeDevice,
  IDeviceRegistration,
  IDeviceHeartbeat,
  IDeviceLog,
  EdgeDeviceType,
  DeviceStatus,
  LogLevel,
} from '@aicamera/shared'

export type {
  IDetection,
  IDetectionRequest,
  IDetectionFilter,
  IDetectionStats,
  ClassificationResult,
  DetectionType,
} from '@aicamera/shared'

export type {
  IImageFile,
  IFileUploadRequest,
  IFileTransferStatus,
  IFileFilter,
  IStorageStats,
  FileStatus,
} from '@aicamera/shared'

export type {
  IUser,
  IUserLogin,
  IUserRegister,
  IAuthResponse,
  IJwtPayload,
  UserRole,
} from '@aicamera/shared'

export type {
  IMqttMessage,
  IWebSocketMessage,
  IWebSocketConnection,
  ISystemAlert,
  AlertType,
  AlertSeverity,
} from '@aicamera/shared'

// Frontend-specific types
export interface DashboardStats {
  devices: {
    total: number
    online: number
    offline: number
    byType: Record<string, number>
  }
  detections: {
    total: number
    today: number
    thisWeek: number
    thisMonth: number
    byType: Record<string, number>
    byDevice: Record<string, number>
    averageConfidence: number
  }
  files: {
    total: number
    totalSize: number
    byStatus: Record<string, number>
    byType: Record<string, number>
  }
}

export interface ChartDataPoint {
  x: string | number
  y: number
  label?: string
}

export interface ChartDataset {
  label: string
  data: number[] | ChartDataPoint[]
  backgroundColor?: string | string[]
  borderColor?: string | string[]
  borderWidth?: number
  fill?: boolean
  tension?: number
}

export interface ChartData {
  labels: string[]
  datasets: ChartDataset[]
}

export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
  width?: string
  align?: 'left' | 'center' | 'right'
  render?: (value: any, row: any) => string | VNode
}

export interface TableRow {
  [key: string]: any
}

export interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

export interface FilterOption {
  label: string
  value: string | number
  count?: number
}

export interface SearchFilter {
  field: string
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'startsWith' | 'endsWith'
  value: any
}

export interface SortConfig {
  field: string
  direction: 'asc' | 'desc'
}

export interface NotificationMessage {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: Date
  read: boolean
  actions?: Array<{
    label: string
    action: () => void
  }>
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'auto'
  language: string
  timezone: string
  notifications: {
    email: boolean
    push: boolean
    desktop: boolean
  }
  dashboard: {
    layout: string
    widgets: string[]
    refreshInterval: number
  }
}

// Form validation types
export interface ValidationRule {
  required?: boolean
  minLength?: number
  maxLength?: number
  min?: number
  max?: number
  pattern?: RegExp
  email?: boolean
  url?: boolean
  custom?: (value: any) => string | true
}

export interface FormField {
  name: string
  label: string
  type: 'text' | 'email' | 'password' | 'number' | 'select' | 'textarea' | 'checkbox' | 'radio' | 'file' | 'date' | 'datetime'
  placeholder?: string
  value?: any
  options?: Array<{ label: string; value: any }>
  rules?: ValidationRule[]
  disabled?: boolean
  readonly?: boolean
  hidden?: boolean
}

export interface FormValidationError {
  field: string
  message: string
}

// API response types
export interface ApiError {
  message: string
  code?: string
  field?: string
  details?: any
}

export interface ApiListResponse<T> {
  data: T[]
  pagination: PaginationInfo
  filters?: Record<string, any>
  sorting?: SortConfig
}

// WebSocket event types
export interface WebSocketEvent {
  event: string
  data: any
  timestamp: string
  source?: string
}

// Route meta types
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    roles?: UserRole[]
    layout?: string
    breadcrumbs?: Array<{
      label: string
      to?: string
    }>
  }
}

// Component prop types
export interface BaseComponentProps {
  class?: string
  style?: Record<string, any>
  loading?: boolean
  disabled?: boolean
}

// Event handler types
export type EventHandler<T = any> = (event: T) => void
export type AsyncEventHandler<T = any> = (event: T) => Promise<void>

// Utility types
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>
export type Required<T, K extends keyof T> = T & Required<Pick<T, K>>
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P]
}

// Vue component types
import type { VNode } from 'vue'

export type ComponentSize = 'sm' | 'md' | 'lg' | 'xl'
export type ComponentVariant = 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
export type ComponentPosition = 'top' | 'bottom' | 'left' | 'right' | 'center'