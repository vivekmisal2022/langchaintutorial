/**
 * Image Storage Service for HANA Cloud
 * 
 * Stores extracted images in a HANA BLOB table and provides
 * retrieval functionality for serving images via REST API.
 * 
 * Supports vector search on image descriptions for page-aware
 * multimodal retrieval.
 */

import * as hdb from 'hdb';
import { AzureOpenAiEmbeddingClient } from '@sap-ai-sdk/langchain';

interface HanaConfig {
  host: string;
  port: number;
  user: string;
  password: string;
}

export interface StoredImage {
  imageId: string;
  documentId: string;
  pageNumber: number;
  mimeType: string;
  width: number;
  height: number;
  description: string;
  createdAt: string;
}

export class ImageStorageService {
  private hanaClient: any = null;
  private hanaConnectPromise: Promise<void> | null = null;
  private ensureTablePromise: Promise<void> | null = null;
  private tableEnsured: boolean = false;
  private embeddingClient: AzureOpenAiEmbeddingClient | null = null;
  private readonly config: {
    hana: HanaConfig;
    imageTableName: string;
    embeddingModel: string;
    resourceGroup: string;
  };

  constructor() {
    this.config = {
      hana: {
        host: process.env.HANA_DB_ADDRESS || '',
        port: parseInt(process.env.HANA_DB_PORT || '443', 10),
        user: process.env.HANA_DB_USER || '',
        password: process.env.HANA_DB_PASSWORD || '',
      },
      imageTableName: process.env.HANA_IMAGE_TABLE || 'LANGCHAIN_DEMO_IMAGES',
      embeddingModel: process.env.EMBEDDING_MODEL || 'text-embedding-3-small',
      resourceGroup: process.env.SAP_AI_RESOURCE_GROUP || 'default',
    };
  }

  /**
   * Get or initialize the embedding client for image descriptions
   * Re-reads env vars at runtime to ensure dotenv has loaded
   */
  private getEmbeddingClient(): AzureOpenAiEmbeddingClient {
    // Re-read env vars at runtime (ESM modules can be instantiated before dotenv runs)
    const embeddingModel = process.env.EMBEDDING_MODEL || this.config.embeddingModel || 'text-embedding-3-small';
    const resourceGroup = process.env.SAP_AI_RESOURCE_GROUP || this.config.resourceGroup || 'default';

    if (!this.embeddingClient) {
      console.log(`Initializing image embedding client with model: ${embeddingModel}, resourceGroup: ${resourceGroup}`);
      this.embeddingClient = new AzureOpenAiEmbeddingClient({
        modelName: embeddingModel,
        resourceGroup: resourceGroup,
      });
    }
    return this.embeddingClient;
  }

  /**
   * Initialize HANA database connection
   */
  private async initHanaConnection(): Promise<void> {
    if (this.hanaClient) return;
    if (this.hanaConnectPromise) return this.hanaConnectPromise;

    // Re-read env vars at connection time.
    // With ESM import hoisting, modules can be instantiated before dotenv config runs.
    // Reading env vars here avoids capturing empty values.
    const host = (process.env.HANA_DB_ADDRESS || this.config.hana.host || '').trim();
    const user = (process.env.HANA_DB_USER || this.config.hana.user || '').trim();
    const password = (process.env.HANA_DB_PASSWORD || this.config.hana.password || '').trim();
    const port = parseInt(process.env.HANA_DB_PORT || String(this.config.hana.port || 443), 10);

    if (!host || !user || !password) {
      throw new Error(
        `Missing HANA connection configuration for image storage. Please set HANA_DB_ADDRESS, HANA_DB_USER, and HANA_DB_PASSWORD in backend-mcp/.env.local (got host="${host}")`
      );
    }

    const connectTimeoutMs = parseInt(process.env.HANA_CONNECT_TIMEOUT_MS || '30000', 10);
    const connectRetries = parseInt(process.env.HANA_CONNECT_RETRIES || '6', 10);
    const connectRetryBaseDelayMs = parseInt(process.env.HANA_CONNECT_RETRY_DELAY_MS || '1000', 10);

    const createClient = () =>
      hdb.createClient({
        host,
        port,
        user,
        password,
        connectTimeout: connectTimeoutMs,
      } as any);

    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    const connectOnce = (client: any) =>
      new Promise<void>((resolve, reject) => {
        let didFinish = false;
        const timer = setTimeout(() => {
          if (didFinish) return;
          didFinish = true;
          try {
            client.disconnect(() => {});
          } catch {
            // ignore
          }
          reject(new Error(`HANA connect timed out after ${connectTimeoutMs}ms`));
        }, connectTimeoutMs);

        client.connect((err: Error) => {
          if (didFinish) return;
          didFinish = true;
          clearTimeout(timer);
          if (err) {
            reject(err);
          } else {
            resolve();
          }
        });
      });

    this.hanaConnectPromise = (async () => {
      let lastErr: any;
      for (let attempt = 0; attempt <= connectRetries; attempt++) {
        const client = createClient();
        try {
          await connectOnce(client);
          this.hanaClient = client;
          console.log('✅ Image storage connected to HANA Cloud');
          return;
        } catch (err) {
          lastErr = err;
          try {
            client.disconnect(() => {});
          } catch {
            // ignore
          }

          const isLast = attempt === connectRetries;
          if (isLast) break;

          const delayMs = Math.min(connectRetryBaseDelayMs * Math.pow(2, attempt), 30000);
          console.warn(
            `Failed to connect to HANA for image storage (attempt ${attempt + 1}/${connectRetries + 1}). Retrying in ${delayMs}ms...`,
            err,
          );
          await sleep(delayMs);
        }
      }

      console.error('Failed to connect to HANA:', lastErr);
      throw lastErr;
    })().finally(() => {
      this.hanaConnectPromise = null;
    });

    return this.hanaConnectPromise;
  }

  private resetHanaConnection(): void {
    if (this.hanaClient) {
      try {
        this.hanaClient.disconnect(() => {});
      } catch {
        // ignore
      }
    }
    this.hanaClient = null;
    this.hanaConnectPromise = null;
  }

  private isTransientHanaError(err: any): boolean {
    const msg = String(err?.message || err || '');
    const code = String(err?.code || '');
    return (
      code === 'EHDBCLOSE' ||
      code === 'EHDBOPENCONN' ||
      msg.includes('EHDBCLOSE') ||
      msg.includes('EHDBOPENCONN') ||
      msg.toLowerCase().includes('connection closed') ||
      msg.includes('No initialization reply received') ||
      msg.toLowerCase().includes('socket hang up') ||
      msg.toLowerCase().includes('timeout')
    );
  }

  /**
   * Ensure the image table exists with the correct schema (including description_embedding column)
   * Uses promise caching to prevent concurrent table creation attempts.
   */
  async ensureImageTable(): Promise<void> {
    // Fast path: table already ensured
    if (this.tableEnsured) return;

    // If another call is already ensuring the table, wait for it
    if (this.ensureTablePromise) return this.ensureTablePromise;

    this.ensureTablePromise = this._doEnsureImageTable();

    try {
      await this.ensureTablePromise;
      this.tableEnsured = true;
    } finally {
      this.ensureTablePromise = null;
    }
  }

  /**
   * Internal implementation of table creation/validation
   */
  private async _doEnsureImageTable(): Promise<void> {
    await this.initHanaConnection();

    let tableExists = false;
    try {
      const checkSQL = `SELECT TOP 1 * FROM "${this.config.imageTableName}"`;
      await this.executeSQL(checkSQL);
      tableExists = true;
      console.log(`✅ Image table ${this.config.imageTableName} exists`);
    } catch (error: any) {
      // Table doesn't exist, will create it
    }

    if (tableExists) {
      // Check if description_embedding column exists
      try {
        const checkColumnSQL = `SELECT TOP 1 "description_embedding" FROM "${this.config.imageTableName}"`;
        await this.executeSQL(checkColumnSQL);
        // Column exists, we're good
      } catch (colError: any) {
        // Column doesn't exist - need to add it or recreate table
        console.log(`⚠️ Image table exists but missing description_embedding column.`);
        console.log(`   Attempting to add column...`);
        
        try {
          const alterSQL = `ALTER TABLE "${this.config.imageTableName}" ADD ("description_embedding" REAL_VECTOR(1536))`;
          await this.executeSQL(alterSQL);
          console.log(`✅ Added description_embedding column to ${this.config.imageTableName}`);
        } catch (alterError: any) {
          console.error(`❌ Failed to add description_embedding column: ${alterError?.message}`);
          console.log(`   You may need to drop and recreate the image table, or re-ingest documents.`);
          console.log(`   To drop the table, run: DROP TABLE "${this.config.imageTableName}"`);
          throw new Error(`Image table schema is outdated. Please drop table "${this.config.imageTableName}" and re-ingest documents to enable image search.`);
        }
      }
      return;
    }

    // Table doesn't exist, create it
    console.log(`Creating image table ${this.config.imageTableName}...`);

    const createTableSQL = `
      CREATE TABLE "${this.config.imageTableName}" (
        "image_id" NVARCHAR(255) PRIMARY KEY,
        "document_id" NVARCHAR(255) NOT NULL,
        "page_number" INTEGER NOT NULL,
        "mime_type" NVARCHAR(64),
        "width" INTEGER,
        "height" INTEGER,
        "description" NCLOB,
        "description_embedding" REAL_VECTOR(1536),
        "image_data" BLOB,
        "created_at" NVARCHAR(64)
      )
    `;
    await this.executeSQL(createTableSQL);
    console.log(`✅ Created image table ${this.config.imageTableName} with description_embedding column`);
  }

  /**
   * Store an image in HANA with description embedding for vector search
   */
  async storeImage(params: {
    imageId: string;
    documentId: string;
    pageNumber: number;
    mimeType: string;
    width: number;
    height: number;
    description: string;
    imageData: Buffer;
  }): Promise<void> {
    await this.ensureImageTable();

    const timestamp = new Date().toISOString();

    // Generate embedding for image description
    let descriptionEmbedding: number[] = [];
    if (params.description && params.description.trim()) {
      try {
        const embeddingClient = this.getEmbeddingClient();
        descriptionEmbedding = await embeddingClient.embedQuery(params.description.slice(0, 8000));
      } catch (embErr) {
        console.warn(`Failed to generate embedding for image ${params.imageId}:`, embErr);
      }
    }

    // Delete existing image with same ID (upsert behavior)
    const deleteSQL = `DELETE FROM "${this.config.imageTableName}" WHERE "image_id" = ?`;
    await this.executePreparedSQL(deleteSQL, [params.imageId]);

    const embeddingString = descriptionEmbedding.length > 0 
      ? `[${descriptionEmbedding.join(',')}]` 
      : null;

    const insertSQL = `
      INSERT INTO "${this.config.imageTableName}"
      ("image_id", "document_id", "page_number", "mime_type", "width", "height", "description", "description_embedding", "image_data", "created_at")
      VALUES (?, ?, ?, ?, ?, ?, ?, TO_REAL_VECTOR(?), ?, ?)
    `;

    await this.executePreparedSQL(insertSQL, [
      params.imageId,
      params.documentId,
      params.pageNumber,
      params.mimeType,
      params.width,
      params.height,
      params.description,
      embeddingString,
      params.imageData,
      timestamp,
    ]);

    console.log(`✅ Stored image ${params.imageId} in HANA with description embedding`);
  }

  /**
   * Retrieve image data by ID
   */
  async getImage(imageId: string): Promise<{ data: Buffer; mimeType: string } | null> {
    await this.initHanaConnection();

    const sql = `
      SELECT "image_data", "mime_type"
      FROM "${this.config.imageTableName}"
      WHERE "image_id" = ?
    `;

    try {
      const rows = await this.executePreparedSQL(sql, [imageId]);
      if (rows && rows.length > 0) {
        const row = rows[0];
        return {
          data: row.IMAGE_DATA || row.image_data,
          mimeType: row.MIME_TYPE || row.mime_type || 'image/png',
        };
      }
      return null;
    } catch (err) {
      console.error(`Error retrieving image ${imageId}:`, err);
      return null;
    }
  }

  /**
   * Get image metadata (without the binary data)
   */
  async getImageMetadata(imageId: string): Promise<StoredImage | null> {
    await this.initHanaConnection();

    const sql = `
      SELECT "image_id", "document_id", "page_number", "mime_type", "width", "height", "description", "created_at"
      FROM "${this.config.imageTableName}"
      WHERE "image_id" = ?
    `;

    try {
      const rows = await this.executePreparedSQL(sql, [imageId]);
      if (rows && rows.length > 0) {
        const row = rows[0];
        return {
          imageId: row.IMAGE_ID || row.image_id,
          documentId: row.DOCUMENT_ID || row.document_id,
          pageNumber: row.PAGE_NUMBER || row.page_number,
          mimeType: row.MIME_TYPE || row.mime_type,
          width: row.WIDTH || row.width,
          height: row.HEIGHT || row.height,
          description: row.DESCRIPTION || row.description,
          createdAt: row.CREATED_AT || row.created_at,
        };
      }
      return null;
    } catch (err) {
      console.error(`Error retrieving image metadata ${imageId}:`, err);
      return null;
    }
  }

  /**
   * List all images for a document
   */
  async listImagesForDocument(documentId: string): Promise<StoredImage[]> {
    await this.initHanaConnection();

    const sql = `
      SELECT "image_id", "document_id", "page_number", "mime_type", "width", "height", "description", "created_at"
      FROM "${this.config.imageTableName}"
      WHERE "document_id" = ?
      ORDER BY "page_number", "image_id"
    `;

    try {
      const rows = await this.executePreparedSQL(sql, [documentId]);
      return (rows || []).map((row: any) => ({
        imageId: row.IMAGE_ID || row.image_id,
        documentId: row.DOCUMENT_ID || row.document_id,
        pageNumber: row.PAGE_NUMBER || row.page_number,
        mimeType: row.MIME_TYPE || row.mime_type,
        width: row.WIDTH || row.width,
        height: row.HEIGHT || row.height,
        description: row.DESCRIPTION || row.description,
        createdAt: row.CREATED_AT || row.created_at,
      }));
    } catch (err) {
      console.error(`Error listing images for document ${documentId}:`, err);
      return [];
    }
  }

  /**
   * Search images by description using vector similarity
   * Supports filtering by document IDs and page numbers for page-aware retrieval
   */
  async searchImagesByDescription(
    query: string,
    options?: {
      k?: number;
      documentIds?: string[];
      pageNumbers?: number[];
      pageRange?: number; // e.g., 1 means include pages ±1 from specified pages
    }
  ): Promise<(StoredImage & { score: number })[]> {
    await this.initHanaConnection();

    const k = options?.k ?? 5;
    const documentIds = options?.documentIds ?? [];
    const pageNumbers = options?.pageNumbers ?? [];
    const pageRange = options?.pageRange ?? 0;

    // Generate query embedding
    const embeddingClient = this.getEmbeddingClient();
    const queryEmbedding = await embeddingClient.embedQuery(query);
    const vectorString = `[${queryEmbedding.join(',')}]`;

    // Build SQL with optional filters
    let sql = `
      SELECT TOP ${k}
        "image_id", "document_id", "page_number", "mime_type", 
        "width", "height", "description", "created_at",
        COSINE_SIMILARITY("description_embedding", TO_REAL_VECTOR(?)) as "score"
      FROM "${this.config.imageTableName}"
      WHERE "description_embedding" IS NOT NULL
    `;

    const params: any[] = [vectorString];

    // Filter by document IDs if specified
    if (documentIds.length > 0) {
      const placeholders = documentIds.map(() => '?').join(',');
      sql += ` AND "document_id" IN (${placeholders})`;
      params.push(...documentIds);
    }

    // Filter by page numbers (with optional range) if specified
    if (pageNumbers.length > 0) {
      if (pageRange > 0) {
        // Include pages within range of specified pages
        const pageConditions = pageNumbers.map(() => 
          `("page_number" BETWEEN ? - ${pageRange} AND ? + ${pageRange})`
        ).join(' OR ');
        sql += ` AND (${pageConditions})`;
        for (const pn of pageNumbers) {
          params.push(pn, pn);
        }
      } else {
        // Exact page match
        const placeholders = pageNumbers.map(() => '?').join(',');
        sql += ` AND "page_number" IN (${placeholders})`;
        params.push(...pageNumbers);
      }
    }

    sql += ` ORDER BY "score" DESC`;

    try {
      const rows = await this.executePreparedSQL(sql, params);
      return (rows || []).map((row: any) => ({
        imageId: row.IMAGE_ID || row.image_id,
        documentId: row.DOCUMENT_ID || row.document_id,
        pageNumber: row.PAGE_NUMBER || row.page_number,
        mimeType: row.MIME_TYPE || row.mime_type,
        width: row.WIDTH || row.width,
        height: row.HEIGHT || row.height,
        description: row.DESCRIPTION || row.description,
        createdAt: row.CREATED_AT || row.created_at,
        score: row.SCORE || row.score || 0,
      }));
    } catch (err) {
      console.error('Error searching images by description:', err);
      return [];
    }
  }

  /**
   * Delete all images for a document
   */
  async deleteImagesForDocument(documentId: string): Promise<number> {
    await this.initHanaConnection();

    const sql = `DELETE FROM "${this.config.imageTableName}" WHERE "document_id" = ?`;

    try {
      const result = await this.executePreparedSQL(sql, [documentId]);
      const count = typeof result === 'number' ? result : 0;
      console.log(`Deleted ${count} images for document ${documentId}`);
      return count;
    } catch (err) {
      console.error(`Error deleting images for document ${documentId}:`, err);
      return 0;
    }
  }

  /**
   * Execute SQL query on HANA
   */
  private async executeSQL(sql: string, params: any[] = []): Promise<any> {
    const run = () =>
      new Promise((resolve, reject) => {
        this.hanaClient.exec(sql, params, (err: Error, rows: any) => {
          if (err) {
            reject(err);
          } else {
            resolve(rows);
          }
        });
      });

    try {
      return await run();
    } catch (err) {
      if (this.isTransientHanaError(err)) {
        this.resetHanaConnection();
        await this.initHanaConnection();
        return await run();
      }
      throw err;
    }
  }

  /**
   * Execute prepared SQL statement on HANA
   */
  private async executePreparedSQL(sql: string, params: any[]): Promise<any> {
    const run = () =>
      new Promise((resolve, reject) => {
        this.hanaClient.prepare(sql, (prepareErr: Error, statement: any) => {
          if (prepareErr) {
            reject(prepareErr);
            return;
          }

          statement.exec(params, (execErr: Error, rows: any) => {
            statement.drop(() => {});

            if (execErr) {
              reject(execErr);
            } else {
              resolve(rows);
            }
          });
        });
      });

    try {
      return await run();
    } catch (err) {
      if (this.isTransientHanaError(err)) {
        this.resetHanaConnection();
        await this.initHanaConnection();
        return await run();
      }
      throw err;
    }
  }
}

export const imageStorageService = new ImageStorageService();
