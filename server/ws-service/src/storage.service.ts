import { Injectable } from '@nestjs/common';
import * as fs from 'fs';
import * as path from 'path';

@Injectable()
export class StorageService {
  private readonly storageImageDir: string;
  private readonly messageLogPath: string;

  constructor() {
    const serverRoot = process.env.STORAGE_ROOT || path.join(process.cwd(), '..');
    this.storageImageDir = path.join(serverRoot, 'storage');
    this.messageLogPath = path.join(serverRoot, 'receive_message.log');
    this.ensureDirectories();
  }

  private ensureDirectories(): void {
    if (!fs.existsSync(this.storageImageDir)) {
      fs.mkdirSync(this.storageImageDir, { recursive: true });
    }
  }

  async saveImage(
    base64Data: string,
    filename?: string,
    cameraId?: string,
  ): Promise<string> {
    const base64 = base64Data.includes(',')
      ? base64Data.split(',')[1]
      : base64Data;
    const buffer = Buffer.from(base64.trim(), 'base64');
    const ext = this.getExtensionFromBuffer(buffer) || '.jpg';
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const safeName = filename || `detection_${timestamp}${ext}`;
    const safeNameClean = safeName.replace(/[^a-zA-Z0-9._-]/g, '_');

    let subDir = this.storageImageDir;
    if (cameraId) {
      subDir = path.join(this.storageImageDir, String(cameraId));
      if (!fs.existsSync(subDir)) {
        fs.mkdirSync(subDir, { recursive: true });
      }
    }

    const filePath = path.join(subDir, safeNameClean);
    fs.writeFileSync(filePath, buffer);
    return filePath;
  }

  private getExtensionFromBuffer(buffer: Buffer): string | null {
    if (buffer[0] === 0xff && buffer[1] === 0xd8) return '.jpg';
    if (buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4e) return '.png';
    if (buffer[0] === 0x47 && buffer[1] === 0x49 && buffer[2] === 0x46) return '.gif';
    if (buffer[0] === 0x52 && buffer[1] === 0x49 && buffer[2] === 0x46) return '.webp';
    return null;
  }

  async saveMessage(content: string): Promise<void> {
    const timestamp = new Date().toISOString();
    const line = `[${timestamp}] ${content}\n`;
    fs.appendFileSync(this.messageLogPath, line);
  }
}
