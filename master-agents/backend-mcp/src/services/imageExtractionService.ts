/**
 * Image Extraction Service for PDF Documents
 * 
 * Extracts images from PDF pages and generates VLM descriptions
 * optimized for financial documents (charts, tables, graphs).
 * 
 * Images are interleaved into the text flow at their approximate positions.
 */

import { AzureOpenAiChatClient } from '@sap-ai-sdk/langchain';
import { HumanMessage } from '@langchain/core/messages';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as crypto from 'crypto';

// Lazy-load pdfjs-dist to avoid startup issues
let pdfjsLib: any = null;

async function getPdfJs() {
  if (!pdfjsLib) {
    // In Node.js, pdfjs-dist recommends using the legacy build.
    // This also avoids runtime warnings and improves compatibility.
    pdfjsLib = await import('pdfjs-dist/legacy/build/pdf.mjs');
  }
  return pdfjsLib;
}

export interface ExtractedImage {
  imageId: string;
  pageNumber: number;
  imageData: Buffer;
  mimeType: string;
  width: number;
  height: number;
  description: string;
}

export interface PageWithImages {
  pageNumber: number;
  text: string;
  textWithImages: string; // Text with image descriptions interleaved
  images: ExtractedImage[];
}

// Configurable minimum image dimensions (read at runtime)
function getMinImageWidth(): number {
  return parseInt(process.env.MIN_IMAGE_WIDTH || '100', 10);
}
function getMinImageHeight(): number {
  return parseInt(process.env.MIN_IMAGE_HEIGHT || '100', 10);
}

// Test mode: limit number of pages to process for image extraction
// Set MAX_IMAGE_PAGES in .env.local to limit (e.g., 3 for testing)
// If not set or 0, all pages are processed
// NOTE: Read at runtime to ensure dotenv has loaded
function getMaxImagePages(): number {
  return parseInt(process.env.MAX_IMAGE_PAGES || '0', 10);
}

// Parallel processing configuration
function getImageAnalysisConcurrency(): number {
  return parseInt(process.env.IMAGE_ANALYSIS_CONCURRENCY || '5', 10);
}
function getImageAnalysisRetries(): number {
  return parseInt(process.env.IMAGE_ANALYSIS_RETRIES || '3', 10);
}
function getImageAnalysisRetryDelayMs(): number {
  return parseInt(process.env.IMAGE_ANALYSIS_RETRY_DELAY_MS || '1000', 10);
}

/**
 * Image analysis response structure
 */
interface ImageAnalysisResult {
  description: string;
  shouldEmbed: boolean;
  reason: string;
}

function normalizeToRgba(data: Uint8Array | Uint8ClampedArray, width: number, height: number): Uint8ClampedArray {
  const pixelCount = width * height;
  const expectedRgbaLen = pixelCount * 4;
  const expectedRgbLen = pixelCount * 3;
  const expectedGrayLen = pixelCount;

  // Some PDFs expose 1-bit image masks as packed bits (length * 8 == pixelCount).
  // If we treat that as bytes, most pixels become 0 -> solid black.
  if (data.length * 8 === pixelCount) {
    const out = new Uint8ClampedArray(expectedRgbaLen);
    for (let p = 0; p < pixelCount; p++) {
      const byteIndex = p >> 3;
      const bitIndex = 7 - (p & 7);
      const bit = ((data[byteIndex] ?? 0) >> bitIndex) & 1;
      const v = bit ? 255 : 0;
      const i = p * 4;
      out[i] = v;
      out[i + 1] = v;
      out[i + 2] = v;
      out[i + 3] = 255;
    }
    return out;
  }

  if (data.length === expectedRgbaLen) {
    return data instanceof Uint8ClampedArray ? data : new Uint8ClampedArray(data);
  }

  const out = new Uint8ClampedArray(expectedRgbaLen);

  if (data.length === expectedRgbLen) {
    for (let i = 0, j = 0; i < expectedRgbaLen && j < expectedRgbLen; i += 4, j += 3) {
      out[i] = data[j] ?? 0;
      out[i + 1] = data[j + 1] ?? 0;
      out[i + 2] = data[j + 2] ?? 0;
      out[i + 3] = 255;
    }
    return out;
  }

  if (data.length === expectedGrayLen) {
    let max = 0;
    for (let j = 0; j < expectedGrayLen; j++) {
      const v = data[j] ?? 0;
      if (v > max) max = v;
      if (max > 1) break;
    }
    const scale = max <= 1 ? 255 : 1;
    for (let i = 0, j = 0; i < expectedRgbaLen && j < expectedGrayLen; i += 4, j += 1) {
      const v = (data[j] ?? 0) * scale;
      out[i] = v;
      out[i + 1] = v;
      out[i + 2] = v;
      out[i + 3] = 255;
    }
    return out;
  }

  const min = Math.min(data.length, expectedRgbaLen);
  for (let i = 0; i < min; i++) {
    out[i] = data[i] ?? 0;
  }
  for (let i = 3; i < expectedRgbaLen; i += 4) {
    if (out[i] === 0) out[i] = 255;
  }
  return out;
}

/**
 * Document-aware VLM prompt for image description with embedding decision
 * Uses document summary to make context-aware embedding decisions
 * Returns JSON with description, shouldEmbed decision, and reason
 */
function buildImageAnalysisPrompt(surroundingText: string, documentSummary?: string): string {
  const summaryContext = documentSummary 
    ? `\n## Document Summary\nThis document is about:\n${documentSummary.slice(0, 1000)}\n`
    : '';

  return `You are an expert document analyst. Analyze this image and decide if it should be embedded in the document's knowledge base.
${summaryContext}
## Surrounding Text Context
This image appears near the following text:
---
${surroundingText.slice(0, 1500)}
---

## Your Task
1. Analyze the image and extract meaningful information
2. Decide whether this image is RELEVANT to the document's topic and should be embedded

## Embedding Decision Guidelines

**EMBED: YES** if the image:
- Contains data (charts, graphs, tables, specifications, diagrams)
- Shows products, equipment, or items directly related to the document's topic
- Contains technical diagrams, schematics, or cutaway views
- Shows facilities, locations, or infrastructure relevant to the content
- Contains text, labels, or annotations with useful information
- Provides visual explanation of concepts discussed in the document

**EMBED: NO** if the image:
- Is purely decorative (backgrounds, borders, abstract patterns)
- Is generic stock photography not specific to the document's topic
- Is too small or low quality to provide useful information
- Is an icon, bullet point, or UI element
- Is a logo used as a separator or decoration
- Shows generic scenes unrelated to the document's specific content

## Output Format
Respond with a JSON object (no markdown code blocks, just raw JSON):
{
  "description": "<detailed description of the image content, including all data, tables in markdown, etc.>",
  "shouldEmbed": true or false,
  "reason": "<brief explanation of why this image is or is not relevant to the document's topic>"
}

Analyze the image now and respond with JSON only:`;
}

export class ImageExtractionService {
  private visionClient: AzureOpenAiChatClient | null = null;
  private readonly resourceGroup: string;
  private readonly visionModel: string;

  constructor() {
    this.resourceGroup = process.env.SAP_AI_RESOURCE_GROUP || 'default';
    this.visionModel = process.env.VISION_MODEL || 'gpt-4.1';
  }

  private getVisionClient(): AzureOpenAiChatClient {
    if (!this.visionClient) {
      console.log(`Initializing vision client with model: ${this.visionModel}`);
      this.visionClient = new AzureOpenAiChatClient({
        modelName: this.visionModel,
        resourceGroup: this.resourceGroup,
        temperature: 0.2,
        max_tokens: 2048,
      });
    }
    return this.visionClient;
  }

  /**
   * Generate a unique image ID
   */
  private generateImageId(documentId: string, pageNumber: number, index: number): string {
    const hash = crypto.createHash('md5')
      .update(`${documentId}_${pageNumber}_${index}_${Date.now()}`)
      .digest('hex')
      .slice(0, 8);
    return `${documentId}_p${pageNumber}_img${index}_${hash}`;
  }

  /**
   * Extract images from a PDF buffer and generate descriptions
   * @param documentSummary Optional document summary to help with context-aware image filtering
   */
  async extractImagesFromPdf(
    pdfBuffer: Buffer,
    documentId: string,
    onProgress?: (message: string) => void,
    documentSummary?: string
  ): Promise<PageWithImages[]> {
    const pdfjs = await getPdfJs();

    // pdfjs-dist expects `Uint8Array` in Node environments (not a Buffer instance)
    const data = new Uint8Array(pdfBuffer.buffer, pdfBuffer.byteOffset, pdfBuffer.byteLength);

    // Load PDF document
    const loadingTask = pdfjs.getDocument({ data });
    const pdfDoc = await loadingTask.promise;
    const totalPages = pdfDoc.numPages;

    // Apply MAX_IMAGE_PAGES limit if set (for testing)
    // Read at runtime to ensure dotenv has loaded
    const maxImagePages = getMaxImagePages();
    const pagesToProcess = maxImagePages > 0 ? Math.min(maxImagePages, totalPages) : totalPages;
    
    if (maxImagePages > 0 && totalPages > maxImagePages) {
      onProgress?.(`⚠️ TEST MODE: Processing only ${pagesToProcess} of ${totalPages} pages for images (MAX_IMAGE_PAGES=${maxImagePages})`);
      console.log(`⚠️ TEST MODE: Limiting image extraction to ${pagesToProcess} pages (MAX_IMAGE_PAGES=${maxImagePages})`);
    } else {
      onProgress?.(`Extracting images from ${pagesToProcess} pages...`);
    }

    const pagesWithImages: PageWithImages[] = [];

    for (let pageNum = 1; pageNum <= pagesToProcess; pageNum++) {
      onProgress?.(`Processing page ${pageNum}/${pagesToProcess}...`);
      
      const page = await pdfDoc.getPage(pageNum);
      
      // Get text content
      const textContent = await page.getTextContent();
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      // Extract images from page, passing surrounding text and document summary for context
      const images = await this.extractImagesFromPage(page, documentId, pageNum, pageText, onProgress, documentSummary);

      // Interleave image descriptions into text
      const textWithImages = this.interleaveImagesIntoText(pageText, images);

      pagesWithImages.push({
        pageNumber: pageNum,
        text: pageText,
        textWithImages,
        images,
      });
    }

    // For remaining pages (beyond MAX_IMAGE_PAGES), just extract text without images
    for (let pageNum = pagesToProcess + 1; pageNum <= totalPages; pageNum++) {
      const page = await pdfDoc.getPage(pageNum);
      const textContent = await page.getTextContent();
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      pagesWithImages.push({
        pageNumber: pageNum,
        text: pageText,
        textWithImages: pageText, // No image processing for these pages
        images: [],
      });
    }

    return pagesWithImages;
  }

  async extractImagesFromPdfPageRange(params: {
    pdfBuffer: Buffer;
    documentId: string;
    startPage: number;
    endPage: number;
    includeVlmAnalysis: boolean;
  }): Promise<{ pageNumber: number; images: Array<{ index: number; width: number; height: number; mimeType: string; buffer: Buffer }> }[]> {
    const { pdfBuffer, documentId, startPage, endPage, includeVlmAnalysis } = params;
    const pdfjs = await getPdfJs();
    const data = new Uint8Array(pdfBuffer.buffer, pdfBuffer.byteOffset, pdfBuffer.byteLength);
    const loadingTask = pdfjs.getDocument({ data });
    const pdfDoc = await loadingTask.promise;

    const totalPages = pdfDoc.numPages;
    const from = Math.max(1, Math.min(startPage, totalPages));
    const to = Math.max(from, Math.min(endPage, totalPages));

    const results: {
      pageNumber: number;
      images: Array<{ index: number; width: number; height: number; mimeType: string; buffer: Buffer }>;
    }[] = [];

    for (let pageNum = from; pageNum <= to; pageNum++) {
      const page = await pdfDoc.getPage(pageNum);
      const textContent = await page.getTextContent();
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();

      const operatorList = await page.getOperatorList();
      const OPS = pdfjs.OPS;
      const images: Array<{ index: number; width: number; height: number; mimeType: string; buffer: Buffer }> = [];

      let imageIndex = 0;
      for (let i = 0; i < operatorList.fnArray.length; i++) {
        const op = operatorList.fnArray[i];
        if (op === OPS.paintImageXObject || op === OPS.paintJpegXObject) {
          const imageName = operatorList.argsArray[i][0];
          const imageData = await this.getImageFromPage(page, imageName);
          if (imageData) {
            if (includeVlmAnalysis) {
              await this.analyzeImage(imageData.buffer, imageData.mimeType, pageText);
            }
            images.push({
              index: imageIndex,
              width: imageData.width,
              height: imageData.height,
              mimeType: imageData.mimeType,
              buffer: imageData.buffer,
            });
          }
          imageIndex++;
        }
      }

      results.push({ pageNumber: pageNum, images });
    }

    return results;
  }

  /**
   * Extract images from a single PDF page with parallel processing
   */
  private async extractImagesFromPage(
    page: any,
    documentId: string,
    pageNumber: number,
    surroundingText: string,
    onProgress?: (message: string) => void,
    documentSummary?: string
  ): Promise<ExtractedImage[]> {
    const images: ExtractedImage[] = [];
    
    try {
      const operatorList = await page.getOperatorList();
      const pdfjs = await getPdfJs();
      const OPS = pdfjs.OPS;

      // First pass: collect all valid image candidates
      interface ImageCandidate {
        index: number;
        imageName: string;
        imageData: { buffer: Buffer; mimeType: string; width: number; height: number };
      }
      const candidates: ImageCandidate[] = [];
      let imageIndex = 0;

      for (let i = 0; i < operatorList.fnArray.length; i++) {
        const op = operatorList.fnArray[i];
        
        // Check for image operations
        if (op === OPS.paintImageXObject || op === OPS.paintJpegXObject) {
          const imageName = operatorList.argsArray[i][0];
          
          try {
            const imageData = await this.getImageFromPage(page, imageName);
            
            if (imageData && imageData.width >= getMinImageWidth() && imageData.height >= getMinImageHeight()) {
              candidates.push({ index: imageIndex, imageName, imageData });
            }
            imageIndex++;
          } catch (imgErr) {
            console.warn(`Failed to extract image ${imageName} from page ${pageNumber}:`, imgErr);
            imageIndex++;
          }
        }
      }

      if (candidates.length === 0) {
        return images;
      }

      onProgress?.(`  Found ${candidates.length} image candidates on page ${pageNumber}, analyzing in parallel...`);

      // Second pass: analyze images in parallel with concurrency limit
      const concurrency = getImageAnalysisConcurrency();
      let skippedCount = 0;
      let processedCount = 0;

      // Process in batches
      for (let batchStart = 0; batchStart < candidates.length; batchStart += concurrency) {
        const batch = candidates.slice(batchStart, batchStart + concurrency);
        
        const batchResults = await Promise.all(
          batch.map(async (candidate) => {
            processedCount++;
            onProgress?.(`  Analyzing image ${processedCount}/${candidates.length} on page ${pageNumber}...`);
            
            const analysis = await this.analyzeImage(
              candidate.imageData.buffer,
              candidate.imageData.mimeType,
              surroundingText,
              documentSummary
            );
            
            return { candidate, analysis };
          })
        );

        // Process results
        for (const { candidate, analysis } of batchResults) {
          if (analysis.shouldEmbed) {
            const imageId = this.generateImageId(documentId, pageNumber, candidate.index);
            
            onProgress?.(`  ✅ Embedding image ${candidate.index + 1}: ${analysis.reason}`);
            
            images.push({
              imageId,
              pageNumber,
              imageData: candidate.imageData.buffer,
              mimeType: candidate.imageData.mimeType,
              width: candidate.imageData.width,
              height: candidate.imageData.height,
              description: analysis.description,
            });
          } else {
            skippedCount++;
            onProgress?.(`  ⏭️ Skipping image ${candidate.index + 1}: ${analysis.reason}`);
          }
        }
      }
      
      if (skippedCount > 0) {
        console.log(`  Page ${pageNumber}: Skipped ${skippedCount} irrelevant images`);
      }
    } catch (err) {
      console.warn(`Error extracting images from page ${pageNumber}:`, err);
    }

    return images;
  }

  /**
   * Get image data from PDF page object
   */
  private async getImageFromPage(
    page: any,
    imageName: string
  ): Promise<{ buffer: Buffer; mimeType: string; width: number; height: number } | null> {
    try {
      const objs = page.objs;
      
      // Try to get the image object
      const imgObj = await new Promise<any>((resolve) => {
        if (objs.get.length >= 2) {
          // Callback-based API
          objs.get(imageName, (data: any) => resolve(data ?? null));
        } else {
          // Direct API
          try {
            resolve(objs.get(imageName));
          } catch {
            resolve(null);
          }
        }
      });

      if (!imgObj) return null;

      const width = imgObj.width;
      const height = imgObj.height;
      
      if (!width || !height) return null;

      // Convert image data to PNG buffer
      let buffer: Buffer;
      let mimeType = 'image/png';

      if (imgObj.data) {
        // Raw image data - need to convert to PNG
        // For simplicity, we'll create a basic PNG from RGBA data
        buffer = await this.createPngFromRgba(imgObj.data, width, height);
      } else if (imgObj.src) {
        // Already encoded (JPEG, etc.)
        if (typeof imgObj.src === 'string' && imgObj.src.startsWith('data:')) {
          const base64Data = imgObj.src.split(',')[1];
          buffer = Buffer.from(base64Data, 'base64');
          mimeType = imgObj.src.split(';')[0].split(':')[1] || 'image/png';
        } else {
          buffer = Buffer.from(imgObj.src);
        }
      } else {
        return null;
      }

      return { buffer, mimeType, width, height };
    } catch (err) {
      console.warn(`Error getting image ${imageName}:`, err);
      return null;
    }
  }

  /**
   * Create a simple PNG from RGBA data
   * Note: This is a simplified implementation. For production, consider using sharp or canvas.
   */
  private async createPngFromRgba(data: Uint8Array | Uint8ClampedArray, width: number, height: number): Promise<Buffer> {
    // For now, we'll use a simple approach - just store as raw data
    // In production, you'd want to use a proper image library like sharp
    
    // Try to use canvas if available
    try {
      const { createCanvas } = await import('@napi-rs/canvas');
      const canvas = createCanvas(width, height);
      const ctx = canvas.getContext('2d');
      const imageData = ctx.createImageData(width, height);

      const rgba = normalizeToRgba(data, width, height);

      for (let i = 0; i < rgba.length; i++) {
        imageData.data[i] = rgba[i] ?? 0;
      }
      
      ctx.putImageData(imageData, 0, 0);
      return canvas.toBuffer('image/png');
    } catch {
      // Fallback: return raw data as buffer (won't be a valid image but can be stored)
      console.warn('Canvas not available, storing raw image data');
      return Buffer.from(data);
    }
  }

  /**
   * Analyze an image using the vision model - returns description + embedding decision
   * Includes retry logic with exponential backoff for rate limiting
   */
  async analyzeImage(
    imageBuffer: Buffer,
    mimeType: string,
    surroundingText: string,
    documentSummary?: string
  ): Promise<ImageAnalysisResult> {
    const maxRetries = getImageAnalysisRetries();
    const baseDelayMs = getImageAnalysisRetryDelayMs();

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const visionClient = this.getVisionClient();
        
        // Convert image to base64
        const base64Image = imageBuffer.toString('base64');
        const dataUrl = `data:${mimeType};base64,${base64Image}`;

        // Build prompt with surrounding text context and document summary
        const prompt = buildImageAnalysisPrompt(surroundingText, documentSummary);

        // Create message with image
        const message = new HumanMessage({
          content: [
            {
              type: 'text',
              text: prompt,
            },
            {
              type: 'image_url',
              image_url: {
                url: dataUrl,
              },
            },
          ],
        });

        const response = await visionClient.invoke([message as any]);
        
        // Extract text content from response
        let content = response.content;
        if (Array.isArray(content)) {
          content = content
            .map((c: any) => (typeof c === 'string' ? c : c?.text ?? ''))
            .join('');
        }
        content = String(content || '');
        
        // Parse JSON response
        try {
          // Clean up potential markdown code blocks
          const jsonStr = content
            .replace(/^```json\s*/i, '')
            .replace(/^```\s*/i, '')
            .replace(/\s*```$/i, '')
            .trim();
          
          const parsed = JSON.parse(jsonStr) as ImageAnalysisResult;
          return {
            description: parsed.description || '[No description]',
            shouldEmbed: parsed.shouldEmbed ?? true, // Default to true if not specified
            reason: parsed.reason || 'No reason provided',
          };
        } catch (parseErr) {
          // If JSON parsing fails, treat as description-only (embed by default)
          console.warn('Failed to parse VLM JSON response, using raw content as description');
          return {
            description: content || '[Image description unavailable]',
            shouldEmbed: true,
            reason: 'JSON parse failed, defaulting to embed',
          };
        }
      } catch (err: any) {
        const isRateLimit = err?.message?.includes('429') || 
                           err?.message?.toLowerCase().includes('rate limit') ||
                           err?.message?.toLowerCase().includes('too many requests');
        const isLastAttempt = attempt === maxRetries;

        if (isRateLimit && !isLastAttempt) {
          const delayMs = baseDelayMs * Math.pow(2, attempt);
          console.warn(`Rate limited on image analysis (attempt ${attempt + 1}/${maxRetries + 1}). Retrying in ${delayMs}ms...`);
          await new Promise(resolve => setTimeout(resolve, delayMs));
          continue;
        }

        console.error('Error analyzing image:', err);
        return {
          description: '[Image analysis unavailable]',
          shouldEmbed: false,
          reason: `Analysis error: ${err?.message || 'Unknown error'}`,
        };
      }
    }

    // Should not reach here, but just in case
    return {
      description: '[Image analysis unavailable]',
      shouldEmbed: false,
      reason: 'Max retries exceeded',
    };
  }

  /**
   * Generate a description of an image using the vision model (legacy method)
   * @deprecated Use analyzeImage instead for smarter filtering
   */
  async describeImage(imageBuffer: Buffer, mimeType: string): Promise<string> {
    const result = await this.analyzeImage(imageBuffer, mimeType, '');
    return result.description;
  }

  /**
   * Interleave image descriptions into the page text
   * Images are inserted at the end of the text with clear markers
   */
  private interleaveImagesIntoText(pageText: string, images: ExtractedImage[]): string {
    if (images.length === 0) {
      return pageText;
    }

    // Build the combined text with image descriptions
    const parts: string[] = [pageText];

    for (const img of images) {
      const imageBlock = `

[IMAGE:${img.imageId}]
${img.description}
[/IMAGE:${img.imageId}]
`;
      parts.push(imageBlock);
    }

    return parts.join('\n');
  }
}

export const imageExtractionService = new ImageExtractionService();
