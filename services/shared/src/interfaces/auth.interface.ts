export interface IUser {
  id: string;
  email: string;
  username: string;
  firstName?: string;
  lastName?: string;
  role: UserRole;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface IUserLogin {
  email: string;
  password: string;
}

export interface IUserRegister {
  email: string;
  username: string;
  password: string;
  firstName?: string;
  lastName?: string;
}

export interface IAuthResponse {
  user: IUser;
  accessToken: string;
  refreshToken?: string;
  expiresIn: number;
}

export interface IJwtPayload {
  sub: string; // user id
  email: string;
  username: string;
  role: UserRole;
  iat: number;
  exp: number;
}

export interface ISession {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
  createdAt: Date;
}

export interface IPasswordReset {
  email: string;
}

export interface IPasswordResetConfirm {
  token: string;
  newPassword: string;
}

export interface IChangePassword {
  currentPassword: string;
  newPassword: string;
}

export interface IUserProfile {
  firstName?: string;
  lastName?: string;
  email?: string;
}

export enum UserRole {
  ADMIN = 'ADMIN',
  OPERATOR = 'OPERATOR',
  USER = 'USER',
}

export interface IPermission {
  resource: string;
  action: string;
  granted: boolean;
}

export const PERMISSIONS = {
  DEVICES: {
    READ: 'devices:read',
    WRITE: 'devices:write',
    DELETE: 'devices:delete',
    MANAGE: 'devices:manage',
  },
  DETECTIONS: {
    READ: 'detections:read',
    WRITE: 'detections:write',
    DELETE: 'detections:delete',
  },
  FILES: {
    READ: 'files:read',
    WRITE: 'files:write',
    DELETE: 'files:delete',
    UPLOAD: 'files:upload',
  },
  USERS: {
    READ: 'users:read',
    WRITE: 'users:write',
    DELETE: 'users:delete',
    MANAGE: 'users:manage',
  },
  SYSTEM: {
    READ: 'system:read',
    WRITE: 'system:write',
    MANAGE: 'system:manage',
  },
} as const;