export interface IImageFile {
  id: string;
  deviceId: string;
  filename: string;
  originalName?: string;
  path: string;
  size: number;
  mimeType: string;
  width?: number;
  height?: number;
  format?: string;
  status: FileStatus;
  thumbnailPath?: string;
  previewPath?: string;
  transferMethod?: string;
  checksum?: string;
  metadata?: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}

export interface IFileUploadRequest {
  deviceId: string;
  filename: string;
  mimeType: string;
  size: number;
  checksum?: string;
  metadata?: Record<string, any>;
}

export interface IFileTransferStatus {
  fileId: string;
  status: FileStatus;
  progress?: number;
  error?: string;
  estimatedTimeRemaining?: number;
}

export interface IFileFilter {
  deviceId?: string;
  status?: FileStatus;
  mimeType?: string;
  startDate?: Date;
  endDate?: Date;
  minSize?: number;
  maxSize?: number;
  hasDetections?: boolean;
  limit?: number;
  offset?: number;
}

export interface IStorageStats {
  totalFiles: number;
  totalSize: number;
  filesByDevice: Record<string, number>;
  filesByStatus: Record<FileStatus, number>;
  filesByType: Record<string, number>;
  diskUsage: {
    used: number;
    available: number;
    total: number;
    percentage: number;
  };
}

export interface ISftpConfig {
  host: string;
  port: number;
  username: string;
  privateKeyPath: string;
  remotePath: string;
  localPath: string;
}

export interface IRsyncConfig {
  source: string;
  destination: string;
  options: string[];
  sshOptions?: {
    host: string;
    port: number;
    username: string;
    privateKeyPath: string;
  };
}

export enum FileStatus {
  UPLOADING = 'UPLOADING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  ERROR = 'ERROR',
  ARCHIVED = 'ARCHIVED',
}