/**
 * REST API routes for document management
 * 
 * These endpoints are for applications to upload, delete, and manage documents.
 * They are NOT MCP tools - MCP tools are only for LLM to retrieve information.
 */

import { Router, Request, Response } from 'express';
import multer from 'multer';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';
import { getDocumentIngestionService } from '../services/documentIngestionService.js';
import { imageExtractionService } from '../services/imageExtractionService.js';
import { imageStorageService } from '../services/imageStorageService.js';
import { logInfo, logError } from '../utils/logger.js';
import {
  createJob,
  getJob,
  subscribeToJob,
  JobState,
} from '../services/ingestionJobManager.js';

const router = Router();

// Configure multer for file uploads
const upload = multer({
  dest: os.tmpdir(),
  limits: {
    fileSize: 50 * 1024 * 1024, // 50MB limit
  },
  fileFilter: (req, file, cb) => {
    const allowedExtensions = ['.pdf', '.txt', '.md', '.docx'];
    const ext = path.extname(file.originalname).toLowerCase();
    
    if (allowedExtensions.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error(`Unsupported file type: ${ext}. Allowed: ${allowedExtensions.join(', ')}`));
    }
  },
});

/**
 * POST /api/documents/upload
 * Upload and ingest one or more documents into HANA Cloud Vector Store
 */
router.post('/upload', upload.array('files', 10), async (req: Request, res: Response) => {
  const files = req.files as Express.Multer.File[];
  const metadata = req.body.metadata ? JSON.parse(req.body.metadata) : undefined;

  const service = getDocumentIngestionService();
  const tenantId = service.getDefaultTenantId();

  logInfo(`Document upload request: ${files?.length || 0} file(s), tenant_id: ${tenantId}`);

  if (!files || files.length === 0) {
    return res.status(400).json({
      success: false,
      error: 'No files provided',
    });
  }

  const jobs: JobState[] = [];

  try {
    await Promise.all(
      files.map(async (file) => {
        const ext = path.extname(file.originalname);
        const newPath = `${file.path}${ext}`;
        await fs.rename(file.path, newPath);

        const job = createJob({ filename: file.originalname, tenantId });
        jobs.push(job);

        const startTime = new Date();

        const perFileMetadata = {
          ...(metadata || {}),
          source_filename: file.originalname,
          original_filename: file.originalname,
        };

        service
          .ingestDocument(newPath, perFileMetadata, tenantId, job.jobId)
          .then((result) => {
            if (result.success) {
              logInfo(
                `Ingestion completed for ${file.originalname} (job ${job.jobId}) with ${result.chunks_created} chunks in ${Date.now() - startTime.getTime()} ms`
              );
            } else {
              logError(
                `Ingestion failed for ${file.originalname} (job ${job.jobId}) after ${Date.now() - startTime.getTime()} ms: ${result.error || 'Unknown error'}`
              );
            }
          })
          .catch((error) => {
            logError(`Failed to ingest ${file.originalname} (job ${job.jobId})`, error);
          })
          .finally(async () => {
            await fs.unlink(newPath).catch(() => {});
          });
      })
    );

    return res.status(202).json({
      success: true,
      message: `Accepted ${jobs.length} document(s) for ingestion`,
      jobs: jobs.map((job) => ({
        job_id: job.jobId,
        filename: job.filename,
        status: job.status,
        stage: job.stage,
        total_chunks: job.totalChunks,
        processed_chunks: job.processedChunks,
        created_at: job.createdAt,
      })),
    });
  } catch (error) {
    logError('Document upload failed', error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

router.post('/debug/extract-page-images', upload.single('file'), async (req: Request, res: Response) => {
  const file = req.file as Express.Multer.File | undefined;
  const startPage = parseInt(String((req.body as any)?.start_page ?? (req.query as any)?.start_page ?? ''), 10);
  const endPage = parseInt(String((req.body as any)?.end_page ?? (req.query as any)?.end_page ?? ''), 10);
  const page = parseInt(String((req.body as any)?.page ?? (req.query as any)?.page ?? ''), 10);
  const includeVlm = String((req.body as any)?.include_vlm ?? (req.query as any)?.include_vlm ?? 'false').toLowerCase() === 'true';
  const includeData = String((req.body as any)?.include_data ?? (req.query as any)?.include_data ?? 'true').toLowerCase() !== 'false';

  if (!file) {
    return res.status(400).json({
      success: false,
      error: 'No file provided (expected multipart field "file")',
    });
  }

  const resolvedStart = Number.isFinite(page) ? page : (Number.isFinite(startPage) ? startPage : NaN);
  const resolvedEnd = Number.isFinite(page) ? page : (Number.isFinite(endPage) ? endPage : resolvedStart);

  if (!Number.isFinite(resolvedStart) || !Number.isFinite(resolvedEnd) || resolvedStart <= 0 || resolvedEnd <= 0) {
    await fs.unlink(file.path).catch(() => {});
    return res.status(400).json({
      success: false,
      error: 'Provide either "page" or "start_page" and optional "end_page" as positive integers',
    });
  }

  try {
    const ext = path.extname(file.originalname || '').toLowerCase();
    if (ext !== '.pdf') {
      return res.status(400).json({
        success: false,
        error: `Unsupported file type: ${ext || '(unknown)'} (expected .pdf)`,
      });
    }

    const pdfBuffer = await fs.readFile(file.path);
    const documentId = `debug_${Date.now()}`;
    const extracted = await imageExtractionService.extractImagesFromPdfPageRange({
      pdfBuffer,
      documentId,
      startPage: resolvedStart,
      endPage: resolvedEnd,
      includeVlmAnalysis: includeVlm,
    });

    const pages = extracted.map((p) => ({
      page_number: p.pageNumber,
      image_count: p.images.length,
      images: p.images.map((img) => {
        const base64 = includeData ? img.buffer.toString('base64') : undefined;
        const data_url = includeData ? `data:${img.mimeType};base64,${base64}` : undefined;
        return {
          index: img.index,
          width: img.width,
          height: img.height,
          mime_type: img.mimeType,
          bytes: img.buffer.length,
          data_url,
        };
      }),
    }));

    return res.status(200).json({
      success: true,
      start_page: resolvedStart,
      end_page: resolvedEnd,
      include_vlm: includeVlm,
      include_data: includeData,
      pages,
    });
  } catch (error) {
    logError('Debug extract-page-images failed', error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  } finally {
    await fs.unlink(file.path).catch(() => {});
  }
});

router.get('/chunks/:chunkId', async (req: Request, res: Response) => {
  const { chunkId } = req.params;

  if (!chunkId) {
    return res.status(400).json({
      success: false,
      error: 'chunkId is required',
    });
  }

  try {
    const service = getDocumentIngestionService();
    const chunk = await service.getChunkById(chunkId);

    if (!chunk) {
      return res.status(404).json({
        success: false,
        error: `Chunk ${chunkId} not found`,
      });
    }

    return res.status(200).json({
      success: true,
      chunk,
    });
  } catch (error) {
    logError(`Failed to retrieve chunk ${chunkId}`, error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * GET /api/documents/images/:imageId/download
 * Download an image by its ID (forces file download)
 */
router.get('/images/:imageId/download', async (req: Request, res: Response) => {
  const { imageId } = req.params;

  if (!imageId) {
    return res.status(400).json({
      success: false,
      error: 'imageId is required',
    });
  }

  try {
    const image = await imageStorageService.getImage(imageId);

    if (!image) {
      return res.status(404).json({
        success: false,
        error: `Image ${imageId} not found`,
      });
    }

    res.setHeader('Content-Type', image.mimeType);
    res.setHeader('Content-Disposition', `attachment; filename="${imageId}"`);
    res.setHeader('Content-Length', image.data.length);

    return res.send(image.data);
  } catch (error) {
    logError(`Failed to download image ${imageId}`, error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * GET /api/documents/images/:imageId/debug
 * Browser-friendly debug view: shows metadata and attempts to render the image.
 */
router.get('/images/:imageId/debug', async (req: Request, res: Response) => {
  const { imageId } = req.params;

  if (!imageId) {
    return res.status(400).send('imageId is required');
  }

  try {
    const [meta, img] = await Promise.all([
      imageStorageService.getImageMetadata(imageId),
      imageStorageService.getImage(imageId),
    ]);

    if (!img) {
      return res.status(404).send(`Image ${imageId} not found`);
    }

    const mime = img.mimeType || 'application/octet-stream';
    const size = img.data?.length ?? 0;
    const headHex = (img.data || Buffer.alloc(0)).subarray(0, 16).toString('hex');
    const base64 = (img.data || Buffer.alloc(0)).toString('base64');

    const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Image Debug: ${imageId}</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 16px; }
      code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
      .row { display: flex; gap: 24px; flex-wrap: wrap; }
      .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; }
      img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 8px; }
    </style>
  </head>
  <body>
    <h1>Image Debug</h1>
    <div class="row">
      <div class="card" style="min-width: 320px; flex: 1;">
        <h2>Metadata</h2>
        <pre>${JSON.stringify(meta, null, 2)}</pre>
        <h2>Binary</h2>
        <div><b>mimeType:</b> <code>${mime}</code></div>
        <div><b>bytes:</b> <code>${size}</code></div>
        <div><b>head (hex, 16 bytes):</b> <code>${headHex}</code></div>
        <div style="margin-top: 12px; display: flex; gap: 12px; flex-wrap: wrap;">
          <a href="/api/documents/images/${imageId}" target="_blank">Open binary</a>
          <a href="/api/documents/images/${imageId}/download">Download</a>
          <a href="/api/documents/images/${imageId}/metadata" target="_blank">Metadata JSON</a>
        </div>
      </div>
      <div class="card" style="min-width: 320px; flex: 2;">
        <h2>Preview</h2>
        <img src="data:${mime};base64,${base64}" alt="${imageId}" />
      </div>
    </div>
  </body>
</html>`;

    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.status(200).send(html);
  } catch (error) {
    logError(`Failed to debug image ${imageId}`, error);
    return res.status(500).send(error instanceof Error ? error.message : String(error));
  }
});

/**
 * GET /api/documents
 * Returns summary information about ingested documents
 */
router.get('/', async (req: Request, res: Response) => {
  try {
    const service = getDocumentIngestionService();
    const tenantId = service.getDefaultTenantId();
    const documents = await service.listDocuments(tenantId);

    return res.status(200).json({
      success: true,
      documents,
    });
  } catch (error) {
    logError('Failed to list documents', error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * DELETE /api/documents/:documentId
 * Deletes all chunks belonging to a specific document
 */
router.delete('/:documentId', async (req: Request, res: Response) => {
  const { documentId } = req.params;

  if (!documentId) {
    return res.status(400).json({
      success: false,
      error: 'documentId is required',
    });
  }

  try {
    const service = getDocumentIngestionService();
    const tenantId = service.getDefaultTenantId();
    const result = await service.deleteDocument(documentId, tenantId);

    return res.status(200).json({
      success: true,
      ...result,
    });
  } catch (error) {
    logError(`Failed to delete document ${documentId}`, error);
    const message = error instanceof Error ? error.message : String(error);
    const status = message.includes('not found') ? 404 : 500;
    return res.status(status).json({
      success: false,
      error: message,
    });
  }
});

/**
 * GET /api/documents/progress/:jobId
 * Returns current progress for a job
 */
router.get('/progress/:jobId', (req: Request, res: Response) => {
  const { jobId } = req.params;
  const job = getJob(jobId);

  if (!job) {
    return res.status(404).json({
      success: false,
      error: `Job ${jobId} not found`,
    });
  }

  return res.status(200).json({
    success: true,
    job,
  });
});

/**
 * GET /api/documents/progress/:jobId/stream
 * Streams job progress updates using Server-Sent Events
 */
router.get('/progress/:jobId/stream', (req: Request, res: Response) => {
  const { jobId } = req.params;
  const job = getJob(jobId);

  if (!job) {
    return res.status(404).json({
      success: false,
      error: `Job ${jobId} not found`,
    });
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
  });

  res.write(`data: ${JSON.stringify(job)}\n\n`);

  const unsubscribe = subscribeToJob(jobId, (state) => {
    res.write(`data: ${JSON.stringify(state)}\n\n`);

    if (state.status === 'completed' || state.status === 'failed') {
      unsubscribe();
      res.write(`event: done\n`);
      res.write(`data: ${JSON.stringify({ job_id: jobId })}\n\n`);
      res.end();
    }
  });

  req.on('close', () => {
    unsubscribe();
  });
});

/**
 * POST /api/documents/search
 * Search for documents (also available as MCP tool for LLM)
 */
router.post('/search', async (req: Request, res: Response) => {
  const defaultKRaw = process.env.DOC_SEARCH_TOP_K_DEFAULT;
  const defaultKParsed = defaultKRaw ? parseInt(defaultKRaw, 10) : NaN;
  const defaultK = Number.isFinite(defaultKParsed) && defaultKParsed > 0 ? defaultKParsed : 10;

  const { query, k = defaultK, document_ids, document_names } = req.body as {
    query?: string;
    k?: number;
    document_ids?: string[];
    document_names?: string[];
  };

  if (!query) {
    return res.status(400).json({
      success: false,
      error: 'Query parameter is required',
    });
  }

  logInfo(
    `Document search request: query="${query}", k=${k}, document_ids=${
      Array.isArray(document_ids) ? document_ids.join(',') : '[]'
    }, document_names=${Array.isArray(document_names) ? document_names.join(',') : '[]'}`,
  );

  try {
    const service = getDocumentIngestionService();
    const tenantId = service.getDefaultTenantId();
    const results = await service.searchDocuments(query, tenantId, k, document_ids, document_names);

    const formattedResults = results.map((doc, idx) => ({
      rank: idx + 1,
      content: doc.pageContent,
      metadata: doc.metadata,
      score: doc.metadata.score,
    }));

    return res.status(200).json({
      success: true,
      query,
      count: results.length,
      results: formattedResults,
    });
  } catch (error) {
    logError('Document search failed', error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * GET /api/documents/images/:imageId
 * Retrieve an image by its ID (serves the binary image data)
 */
router.get('/images/:imageId', async (req: Request, res: Response) => {
  const { imageId } = req.params;

  if (!imageId) {
    return res.status(400).json({
      success: false,
      error: 'imageId is required',
    });
  }

  try {
    const image = await imageStorageService.getImage(imageId);

    if (!image) {
      return res.status(404).json({
        success: false,
        error: `Image ${imageId} not found`,
      });
    }

    // Set appropriate content type and cache headers
    res.setHeader('Content-Type', image.mimeType);
    res.setHeader('Cache-Control', 'public, max-age=86400'); // Cache for 1 day
    res.setHeader('Content-Length', image.data.length);

    return res.send(image.data);
  } catch (error) {
    logError(`Failed to retrieve image ${imageId}`, error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * GET /api/documents/images/:imageId/metadata
 * Retrieve image metadata (without binary data)
 */
router.get('/images/:imageId/metadata', async (req: Request, res: Response) => {
  const { imageId } = req.params;

  if (!imageId) {
    return res.status(400).json({
      success: false,
      error: 'imageId is required',
    });
  }

  try {
    const metadata = await imageStorageService.getImageMetadata(imageId);

    if (!metadata) {
      return res.status(404).json({
        success: false,
        error: `Image ${imageId} not found`,
      });
    }

    return res.status(200).json({
      success: true,
      image: metadata,
    });
  } catch (error) {
    logError(`Failed to retrieve image metadata ${imageId}`, error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

/**
 * GET /api/documents/:documentId/images
 * List all images for a specific document
 */
router.get('/:documentId/images', async (req: Request, res: Response) => {
  const { documentId } = req.params;

  if (!documentId) {
    return res.status(400).json({
      success: false,
      error: 'documentId is required',
    });
  }

  try {
    const images = await imageStorageService.listImagesForDocument(documentId);

    return res.status(200).json({
      success: true,
      document_id: documentId,
      count: images.length,
      images: images.map(img => ({
        image_id: img.imageId,
        page_number: img.pageNumber,
        mime_type: img.mimeType,
        width: img.width,
        height: img.height,
        description: img.description.slice(0, 200) + (img.description.length > 200 ? '...' : ''),
        created_at: img.createdAt,
      })),
    });
  } catch (error) {
    logError(`Failed to list images for document ${documentId}`, error);
    return res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

export default router;
