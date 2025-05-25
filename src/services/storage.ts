import { db } from '../db/pgClient';

// Types
interface StorageFile {
  id: string;
  bucket: string;
  name: string;
  size: number;
  mime_type: string;
  storage_path: string;
  metadata: any;
  created_at: Date;
  updated_at: Date;
}

interface UploadOptions {
  contentType?: string;
  metadata?: any;
  upsert?: boolean;
}

interface Bucket {
  id: string;
  name: string;
  public: boolean;
  file_size_limit: number;
  allowed_mime_types: string[];
}

// Configuration
const STORAGE_BASE_PATH = import.meta.env.VITE_STORAGE_PATH || './storage';
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB default

export class StorageService {
  private static instance: StorageService;

  private constructor() {}

  public static getInstance(): StorageService {
    if (!StorageService.instance) {
      StorageService.instance = new StorageService();
    }
    return StorageService.instance;
  }

  // Upload a file
  async upload(
    bucket: string,
    path: string,
    file: File | Blob | ArrayBuffer,
    options: UploadOptions = {}
  ): Promise<StorageFile> {
    try {
      // Check bucket exists and get its configuration
      const bucketConfig = await this.getBucket(bucket);
      if (!bucketConfig) {
        throw new Error(`Bucket '${bucket}' does not exist`);
      }

      // Validate file size
      const fileSize = file instanceof File ? file.size : 
                      file instanceof Blob ? file.size : 
                      (file as ArrayBuffer).byteLength;

      if (bucketConfig.file_size_limit && fileSize > bucketConfig.file_size_limit) {
        throw new Error(`File size exceeds bucket limit of ${bucketConfig.file_size_limit} bytes`);
      }

      // Validate mime type
      const mimeType = options.contentType || 
                      (file instanceof File ? file.type : 'application/octet-stream');

      if (bucketConfig.allowed_mime_types.length > 0 && 
          !bucketConfig.allowed_mime_types.includes(mimeType)) {
        throw new Error(`File type '${mimeType}' not allowed in this bucket`);
      }

      // Convert file to base64 for storage in DB (in production, use external storage)
      const fileData = await this.fileToBase64(file);
      
      // Generate storage path
      const storagePath = `${bucket}/${path}`;

      // Check if file exists (for upsert)
      if (options.upsert) {
        const existing = await this.getFile(bucket, path);
        if (existing) {
          // Update existing file
          const updated = await db.queryOne<StorageFile>(
            `UPDATE storage.files 
             SET size = $3, mime_type = $4, storage_path = $5, metadata = $6, updated_at = NOW()
             WHERE bucket = $1 AND name = $2
             RETURNING *`,
            [bucket, path, fileSize, mimeType, fileData, options.metadata || {}]
          );
          return updated!;
        }
      }

      // Insert new file
      const result = await db.queryOne<StorageFile>(
        `INSERT INTO storage.files (bucket, name, size, mime_type, storage_path, metadata)
         VALUES ($1, $2, $3, $4, $5, $6)
         RETURNING *`,
        [bucket, path, fileSize, mimeType, fileData, options.metadata || {}]
      );

      if (!result) {
        throw new Error('Failed to store file');
      }

      return result;
    } catch (error) {
      console.error('Upload error:', error);
      throw error;
    }
  }

  // Download a file
  async download(bucket: string, path: string): Promise<Blob> {
    try {
      const file = await this.getFile(bucket, path);
      if (!file) {
        throw new Error('File not found');
      }

      // Convert base64 back to blob
      const blob = await this.base64ToBlob(file.storage_path, file.mime_type);
      return blob;
    } catch (error) {
      console.error('Download error:', error);
      throw error;
    }
  }

  // Get file metadata
  async getFile(bucket: string, path: string): Promise<StorageFile | null> {
    try {
      const file = await db.queryOne<StorageFile>(
        'SELECT * FROM storage.files WHERE bucket = $1 AND name = $2',
        [bucket, path]
      );
      return file;
    } catch (error) {
      console.error('Get file error:', error);
      throw error;
    }
  }

  // List files in a bucket
  async listFiles(
    bucket: string,
    options: { prefix?: string; limit?: number; offset?: number } = {}
  ): Promise<StorageFile[]> {
    try {
      let sql = 'SELECT * FROM storage.files WHERE bucket = $1';
      const params: any[] = [bucket];

      if (options.prefix) {
        sql += ' AND name LIKE $2';
        params.push(`${options.prefix}%`);
      }

      sql += ' ORDER BY created_at DESC';

      if (options.limit) {
        sql += ` LIMIT ${options.limit}`;
      }

      if (options.offset) {
        sql += ` OFFSET ${options.offset}`;
      }

      const files = await db.query<StorageFile>(sql, params);
      return files;
    } catch (error) {
      console.error('List files error:', error);
      throw error;
    }
  }

  // Delete a file
  async deleteFile(bucket: string, path: string): Promise<void> {
    try {
      await db.query(
        'DELETE FROM storage.files WHERE bucket = $1 AND name = $2',
        [bucket, path]
      );
    } catch (error) {
      console.error('Delete file error:', error);
      throw error;
    }
  }

  // Create a bucket
  async createBucket(
    name: string,
    options: {
      public?: boolean;
      fileSizeLimit?: number;
      allowedMimeTypes?: string[];
    } = {}
  ): Promise<Bucket> {
    try {
      const result = await db.queryOne<Bucket>(
        `INSERT INTO storage.buckets (name, public, file_size_limit, allowed_mime_types)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (name) DO NOTHING
         RETURNING *`,
        [
          name,
          options.public || false,
          options.fileSizeLimit || null,
          options.allowedMimeTypes || []
        ]
      );

      if (!result) {
        // Bucket already exists
        const existing = await this.getBucket(name);
        return existing!;
      }

      return result;
    } catch (error) {
      console.error('Create bucket error:', error);
      throw error;
    }
  }

  // Get bucket configuration
  async getBucket(name: string): Promise<Bucket | null> {
    try {
      const bucket = await db.queryOne<Bucket>(
        'SELECT * FROM storage.buckets WHERE name = $1',
        [name]
      );
      return bucket;
    } catch (error) {
      console.error('Get bucket error:', error);
      throw error;
    }
  }

  // Get public URL for a file
  getPublicUrl(bucket: string, path: string): string {
    // In production, this would return a CDN URL
    return `/api/storage/${bucket}/${path}`;
  }

  // Helper methods
  private async fileToBase64(file: File | Blob | ArrayBuffer): Promise<string> {
    if (file instanceof ArrayBuffer) {
      return btoa(String.fromCharCode(...new Uint8Array(file)));
    }

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file as Blob);
    });
  }

  private async base64ToBlob(base64: string, mimeType: string): Promise<Blob> {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  }

  // Get storage statistics
  async getStorageStats(userId?: string): Promise<{
    total_files: number;
    total_size: number;
    buckets: Array<{ name: string; file_count: number; total_size: number }>;
  }> {
    try {
      let userClause = userId ? 'WHERE user_id = $1' : '';
      let params = userId ? [userId] : [];

      // Get total stats
      const totalStats = await db.queryOne<any>(
        `SELECT COUNT(*) as total_files, COALESCE(SUM(size), 0) as total_size
         FROM storage.files ${userClause}`,
        params
      );

      // Get per-bucket stats
      const bucketStats = await db.query<any>(
        `SELECT 
          bucket as name,
          COUNT(*) as file_count,
          COALESCE(SUM(size), 0) as total_size
         FROM storage.files ${userClause}
         GROUP BY bucket`,
        params
      );

      return {
        total_files: parseInt(totalStats?.total_files || 0),
        total_size: parseInt(totalStats?.total_size || 0),
        buckets: bucketStats
      };
    } catch (error) {
      console.error('Get storage stats error:', error);
      throw error;
    }
  }
}

// Export singleton instance
export const storageService = StorageService.getInstance();