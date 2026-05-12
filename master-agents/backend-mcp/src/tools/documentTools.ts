/**
 * MCP tools for document search using HANA Cloud Vector Store
 * 
 * Note: Document upload/deletion are REST API endpoints, not MCP tools.
 * MCP tools are for LLM to retrieve information during conversations.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { getDocumentIngestionService } from '../services/documentIngestionService.js';
import { imageStorageService } from '../services/imageStorageService.js';
import { logInfo } from '../utils/logger.js';

/**
 * Register document search tool (for LLM to retrieve context during conversations)
 */
export function registerDocumentSearchTool(server: McpServer): void {

  function getDefaultTopK(): number {
    const raw = process.env.DOC_SEARCH_TOP_K_DEFAULT;
    const n = raw ? parseInt(raw, 10) : NaN;
    return Number.isFinite(n) && n > 0 ? n : 10;
  }

  // 1) Header-level document search: operate only on summaries in the header table
  //    Returns document metadata including document_id, title, and summary.
  server.tool(
    'search_document_headers',
    'Search documents at the header level using their LLM-generated summaries. Use this to discover which documents are relevant and obtain their document_ids, titles, and summaries before doing detailed content retrieval.',
    {
      query: z.string().describe('Search query text'),
      k: z
        .number()
        .optional()
        .default(10)
        .describe('Number of documents to retrieve based on header summaries (default: 10)'),
    },
    async ({ query, k }) => {
      logInfo(`Tool: search_document_headers | query: ${query}, k: ${k}`);

      try {
        const service = getDocumentIngestionService();
        const tenantId = service.getDefaultTenantId();
        const documents = await service.searchDocumentsByHeader(query, tenantId, k);

        const formatted = documents.map((doc, idx) => ({
          rank: idx + 1,
          document: doc,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  query,
                  document_count: documents.length,
                  results: formatted,
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('Header document search failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error: error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    }
  );

  // 2) Content-level search: search within document chunks, optionally filtered by document_ids
  server.tool(
    'search_document_content',
    'Search within document content chunks using semantic similarity. Use this to retrieve specific passages from documents. Optionally provide document_ids (from a header search) to restrict the search to particular documents. E.g. ["f66d867e225e3ca91142d3476ad93d69", "c76d867e225e3ca91142d3476ad93d69", ...] and/or document names/ titles or filenames in parameter "document_names" like ["ABC-Bank- 2024-External.docx", "Banking Expense Policies", ...].',
    {
      query: z.string().describe('Search query text'),
      k: z
        .number()
        .optional()
        .describe('Number of chunks to return (default: DOC_SEARCH_TOP_K_DEFAULT or 10)'),
      document_ids: z
        .array(z.string())
        .optional()
        .describe('Optional list of document IDs to restrict the search to specific documents'),
      document_names: z
        .array(z.string())
        .optional()
        .describe('Optional list of document names (filenames) to restrict the search when IDs are not available'),
    },
    async ({ query, k, document_ids, document_names }) => {
      const resolvedK = k ?? getDefaultTopK();
      logInfo(
        `Tool: search_document_content | query: ${query}, k: ${resolvedK}, document_ids=${
          Array.isArray(document_ids) ? document_ids.join(',') : '[]'
        }, document_names=${Array.isArray(document_names) ? document_names.join(',') : '[]'}`,
      );

      try {
        const service = getDocumentIngestionService();
        const tenantId = service.getDefaultTenantId();
        const results = await service.searchDocuments(query, tenantId, resolvedK, document_ids, document_names);

        const formattedResults = results.map((doc, idx) => ({
          rank: idx + 1,
          content: doc.pageContent,
          metadata: doc.metadata,
          score: (doc.metadata as any)?.score,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  query,
                  count: results.length,
                  results: formattedResults,
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('Document content search failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error:
                    error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    }
  );

  server.tool(
    'get_document_segment',
    'Retrieve a specific part of a document by document_id and either chunk_index (0-based, 0 = first chunk) or page_number (1-based). Use this when you want to retrieve additional context adjacent to a document chunk or page.',
    {
      document_id: z.string().describe('Document ID to retrieve from'),
      chunk_index: z
        .number()
        .int()
        .optional()
        .describe('0-based chunk index within the document (0 = first chunk). Use this when pages are not meaningful (e.g. docx).'),
      page_number: z
        .number()
        .int()
        .optional()
        .describe('1-based page number within the document. Returns all chunks for that page.'),
    },
    async ({ document_id, chunk_index, page_number }) => {
      logInfo(
        `Tool: get_document_segment | document_id=${document_id}, chunk_index=${
          chunk_index ?? 'null'
        }, page_number=${page_number ?? 'null'}`,
      );

      if ((chunk_index == null && page_number == null) || (chunk_index != null && page_number != null)) {
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error:
                    'You must provide exactly one of chunk_index or page_number (but not both).',
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }

      try {
        const service = getDocumentIngestionService();
        const tenantId = service.getDefaultTenantId();
        const segments = await service.getDocumentSegments(
          document_id,
          { chunkIndex: chunk_index ?? undefined, pageNumber: page_number ?? undefined },
          tenantId,
        );

        const formatted = segments.map((doc, idx) => ({
          index: idx,
          content: doc.pageContent,
          metadata: doc.metadata,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  document_id,
                  chunk_index,
                  page_number,
                  segment_count: segments.length,
                  segments: formatted,
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('get_document_segment failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error: error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    },
  );

  // 4) Page-aware multimodal search: search text chunks first, then find relevant images from those pages
  server.tool(
    'search_with_images',
    `Page-aware multimodal search. Searches text chunks first, then finds relevant images from the same pages (±1 page).
This is the RECOMMENDED tool when you need both text content AND images. It ensures images are contextually related to the text.
Returns:
- Text chunks matching the query (with page numbers)
- Images from those pages that also match the query by their visual descriptions
Use the image markdown syntax to display images: ![description](image:imageId)`,
    {
      query: z.string().describe('Search query text'),
      text_k: z
        .number()
        .optional()
        .default(5)
        .describe('Number of text chunks to retrieve (default: 5)'),
      image_k: z
        .number()
        .optional()
        .default(3)
        .describe('Number of images to retrieve per query (default: 3)'),
      document_ids: z
        .array(z.string())
        .optional()
        .describe('Optional list of document IDs to restrict the search'),
      document_names: z
        .array(z.string())
        .optional()
        .describe('Optional list of document names to restrict the search'),
      page_range: z
        .number()
        .optional()
        .default(1)
        .describe('Include images from pages within this range of text chunk pages (default: 1, meaning ±1 page)'),
    },
    async ({ query, text_k, image_k, document_ids, document_names, page_range }) => {
      logInfo(
        `Tool: search_with_images | query: ${query}, text_k: ${text_k}, image_k: ${image_k}, page_range: ${page_range}`,
      );

      try {
        const service = getDocumentIngestionService();
        const tenantId = service.getDefaultTenantId();

        // Step 1: Search text chunks
        const textResults = await service.searchDocuments(
          query,
          tenantId,
          text_k,
          document_ids,
          document_names
        );

        // Extract unique document IDs and page numbers from text results
        const docPages = new Map<string, Set<number>>();
        for (const doc of textResults) {
          const meta = doc.metadata as Record<string, any>;
          const docId = meta.document_id;
          const pageNum = meta.page_number;
          if (docId && typeof pageNum === 'number') {
            if (!docPages.has(docId)) {
              docPages.set(docId, new Set());
            }
            docPages.get(docId)!.add(pageNum);
          }
        }

        // Step 2: Search images filtered by those documents and pages
        const uniqueDocIds = Array.from(docPages.keys());
        const allPageNumbers = Array.from(
          new Set(Array.from(docPages.values()).flatMap((s) => Array.from(s)))
        );

        let imageResults: Array<{
          imageId: string;
          documentId: string;
          pageNumber: number;
          description: string;
          score: number;
          width: number;
          height: number;
          mimeType: string;
        }> = [];

        if (uniqueDocIds.length > 0 && allPageNumbers.length > 0) {
          const images = await imageStorageService.searchImagesByDescription(query, {
            k: image_k,
            documentIds: uniqueDocIds,
            pageNumbers: allPageNumbers,
            pageRange: page_range,
          });

          imageResults = images.map((img) => ({
            imageId: img.imageId,
            documentId: img.documentId,
            pageNumber: img.pageNumber,
            description: img.description,
            score: img.score,
            width: img.width,
            height: img.height,
            mimeType: img.mimeType,
          }));
        }

        // Format text results
        const formattedTextResults = textResults.map((doc, idx) => {
          const meta = doc.metadata as Record<string, any>;
          return {
            rank: idx + 1,
            content: doc.pageContent,
            document_id: meta.document_id,
            page_number: meta.page_number,
            title: meta.title,
            score: meta.score,
          };
        });

        // Format image results with usage hint
        const formattedImageResults = imageResults.map((img, idx) => ({
          rank: idx + 1,
          image_id: img.imageId,
          document_id: img.documentId,
          page_number: img.pageNumber,
          description: img.description,
          score: img.score,
          markdown_syntax: `![${(img.description || 'Image').slice(0, 50)}](image:${img.imageId})`,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  query,
                  text_results: {
                    count: formattedTextResults.length,
                    chunks: formattedTextResults,
                  },
                  image_results: {
                    count: formattedImageResults.length,
                    images: formattedImageResults,
                    note: 'Images are from the same pages (±page_range) as the text chunks and match the query by description',
                  },
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('search_with_images failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error: error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    }
  );

  // 5) Search images by description: semantic search on image descriptions
  server.tool(
    'search_images',
    `PREFERRED tool for finding images. Searches images by their visual content descriptions using semantic similarity.
Use this FIRST when looking for specific types of images (e.g., "engine diagram", "torque curve graph", "product photo").
This is much faster and more accurate than browsing all images with get_document_images.
Returns the most relevant images ranked by similarity score.
To display an image, use markdown syntax: ![description](image:imageId)`,
    {
      query: z.string().describe('Search query describing the type of image you need (e.g., "engine performance graph", "transmission diagram")'),
      k: z
        .number()
        .optional()
        .default(5)
        .describe('Number of images to retrieve (default: 5)'),
      document_ids: z
        .array(z.string())
        .optional()
        .describe('Optional list of document IDs to restrict the search'),
    },
    async ({ query, k, document_ids }) => {
      logInfo(`Tool: search_images | query: ${query}, k: ${k}`);

      try {
        const images = await imageStorageService.searchImagesByDescription(query, {
          k,
          documentIds: document_ids,
        });

        const formattedResults = images.map((img, idx) => ({
          rank: idx + 1,
          image_id: img.imageId,
          document_id: img.documentId,
          page_number: img.pageNumber,
          description: img.description,
          score: img.score,
          width: img.width,
          height: img.height,
          markdown_syntax: `![${(img.description || 'Image').slice(0, 50)}](image:${img.imageId})`,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  query,
                  count: formattedResults.length,
                  images: formattedResults,
                  usage_hint: 'To display an image, use: ![description](image:imageId)',
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('search_images failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error: error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    }
  );

  // 6) Get document images: retrieve image metadata for a document
  //    Use search_images instead when looking for specific types of images
  server.tool(
    'get_document_images',
    `List all images from a document or specific page. Use this ONLY when you need to see ALL images from a document.
WARNING: For finding specific images (e.g., "engine graph", "diagram"), use search_images instead - it's faster and more accurate.
This tool is best for: getting a complete inventory of images, or when you already know the exact page number.
To display an image, use markdown syntax: ![description](image:imageId)`,
    {
      document_id: z.string().describe('Document ID to get images for'),
      page_number: z
        .number()
        .int()
        .optional()
        .describe('Optional: filter to images from a specific page (1-based). Omit to get ALL images.'),
    },
    async ({ document_id, page_number }) => {
      logInfo(
        `Tool: get_document_images | document_id=${document_id}, page_number=${page_number ?? 'all'}`,
      );

      try {
        const images = await imageStorageService.listImagesForDocument(document_id);
        
        // Filter by page if specified
        const filtered = page_number 
          ? images.filter(img => img.pageNumber === page_number)
          : images;

        const formatted = filtered.map((img) => ({
          image_id: img.imageId,
          page_number: img.pageNumber,
          description: img.description,
          width: img.width,
          height: img.height,
          mime_type: img.mimeType,
          // Include markdown syntax hint for easy copy-paste
          markdown_syntax: `![${img.description?.slice(0, 50) || 'Image'}](image:${img.imageId})`,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: true,
                  document_id,
                  image_count: formatted.length,
                  images: formatted,
                  usage_hint: 'To display an image in your response, use: ![description](image:imageId)',
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        console.error('get_document_images failed:', error);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(
                {
                  success: false,
                  error: error instanceof Error ? error.message : String(error),
                },
                null,
                2,
              ),
            },
          ],
          isError: true,
        };
      }
    },
  );
}
