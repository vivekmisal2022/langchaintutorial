import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { Perplexity } from '@perplexity-ai/perplexity_ai';
import { resolveDeploymentUrl } from '@sap-ai-sdk/ai-api';
import { z } from 'zod';

import { registerToolWithLogging } from '../utils/toolLogger.js';

// Module-level cache for Perplexity clients and OAuth2 token
// Cached for the lifetime of the server process (perfect for workshop duration)
// Separate caches for sonar and sonar-pro models
let cachedClientSonar: Perplexity | null = null;
let cachedClientSonarPro: Perplexity | null = null;
let cachedToken: string | null = null;
let cachedDeploymentUrlSonar: string | null = null;
let cachedDeploymentUrlSonarPro: string | null = null;

const webSearchSchema = z.object({
  query: z.string().describe('The search query or research question'),
  max_results: z.number().optional().describe('Maximum number of results to return (default: 5)'),
});

const webSearchSchemaShape = webSearchSchema.shape;

const webSearchResultSchema = z.object({
  answer: z.string().describe('The synthesized answer from web research'),
  sources: z.array(z.string()).optional().describe('URLs of sources used'),
});

const webSearchResultSchemaShape = webSearchResultSchema.shape;

type WebSearchInput = z.infer<typeof webSearchSchema>;
type WebSearchOutput = z.infer<typeof webSearchResultSchema>;

/**
 * Creates a Perplexity client configured for SAP Generative AI Hub
 * Uses SAP AI SDK for automatic authentication and endpoint resolution
 * Caches client, token, and deployment URL for the lifetime of the server process
 * 
 * @param modelName - The model to use ('sonar' for quick search, 'sonar-pro' for deep research)
 */
async function createPerplexityClient(modelName: 'sonar' | 'sonar-pro' = 'sonar'): Promise<Perplexity> {
  const isSonarPro = modelName === 'sonar-pro';
  const cachedClient = isSonarPro ? cachedClientSonarPro : cachedClientSonar;
  const toolName = isSonarPro ? 'WebResearch' : 'WebSearch';

  // Return cached client if available (fast path)
  if (cachedClient) {
    console.log(`[${toolName}] Using cached Perplexity client (${modelName})`);
    return cachedClient;
  }

  console.log(`[${toolName}] Initializing new Perplexity client (${modelName})...`);

  if (!process.env.AICORE_SERVICE_KEY) {
    throw new Error(
      'AICORE_SERVICE_KEY environment variable is required for web search. ' +
      'Please configure your SAP AI Core service key in .env file.'
    );
  }

  // Get the appropriate deployment URL cache
  let cachedDeploymentUrl = isSonarPro ? cachedDeploymentUrlSonarPro : cachedDeploymentUrlSonar;

  // Resolve deployment URL (cache for reuse)
  if (!cachedDeploymentUrl) {
    console.log(`[${toolName}] Resolving deployment URL for ${modelName}...`);
    cachedDeploymentUrl = await resolveDeploymentUrl({
      scenarioId: 'foundation-models',
      model: {
        name: modelName,
        // Don't specify version - SDK will find the deployed version
      },
      resourceGroup: process.env.SAP_AI_RESOURCE_GROUP || 'default',
    }) || '';

    if (!cachedDeploymentUrl) {
      throw new Error(
        `Could not resolve Perplexity deployment URL for ${modelName}. ` +
        `Ensure Perplexity (${modelName} model) is deployed in your SAP AI Core instance.`
      );
    }

    // Store in the appropriate cache
    if (isSonarPro) {
      cachedDeploymentUrlSonarPro = cachedDeploymentUrl;
    } else {
      cachedDeploymentUrlSonar = cachedDeploymentUrl;
    }
    console.log(`[${toolName}] Deployment URL resolved and cached`);
  }

  // Get OAuth2 token (cache for reuse - shared between both models)
  if (!cachedToken) {
    console.log(`[${toolName}] Requesting OAuth2 token...`);
    const serviceKey = JSON.parse(process.env.AICORE_SERVICE_KEY);
    const tokenUrl = `${serviceKey.url}/oauth/token`;
    
    const tokenResponse = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'client_credentials',
        client_id: serviceKey.clientid,
        client_secret: serviceKey.clientsecret,
      }),
    });

    if (!tokenResponse.ok) {
      throw new Error(`Failed to obtain OAuth2 token: ${tokenResponse.statusText}`);
    }

    const tokenData = await tokenResponse.json();
    cachedToken = tokenData.access_token;
    console.log(`[${toolName}] OAuth2 token obtained and cached`);
  }

  // Create and cache Perplexity client
  const newClient = new Perplexity({
    baseURL: cachedDeploymentUrl,
    defaultHeaders: {
      'Authorization': `Bearer ${cachedToken}`,
      'AI-Resource-Group': process.env.SAP_AI_RESOURCE_GROUP || 'default',
    },
    apiKey: 'not-used', // Required by SDK but not used with custom auth
  });

  // Store in the appropriate cache
  if (isSonarPro) {
    cachedClientSonarPro = newClient;
  } else {
    cachedClientSonar = newClient;
  }

  console.log(`[${toolName}] Perplexity client created and cached`);
  return newClient;
}

/**
 * Mock web search function for testing without SAP AI Hub connection
 */
async function mockWebSearch(query: string, _maxResults = 5): Promise<WebSearchOutput> {
  // Simulate API delay
  await new Promise(resolve => setTimeout(resolve, 500));

  const mockAnswers: Record<string, WebSearchOutput> = {
    'latest AI developments': {
      answer: 'Recent AI developments include GPT-4 Turbo with improved reasoning, Google Gemini Ultra for multimodal tasks, and advancements in open-source models like Llama 3. Key trends focus on AI safety, efficiency, and enterprise integration.',
      sources: [
        'https://openai.com/blog/gpt-4-turbo',
        'https://deepmind.google/technologies/gemini/',
        'https://ai.meta.com/llama/',
      ],
    },
    'SAP BTP': {
      answer: 'SAP Business Technology Platform (BTP) is an integrated offering that brings together data management, analytics, AI, and application development. It provides a unified environment for extending SAP applications and building new cloud-native solutions.',
      sources: [
        'https://www.sap.com/products/technology-platform.html',
        'https://help.sap.com/docs/btp',
      ],
    },
  };

  // Find best match or return generic response
  const lowerQuery = query.toLowerCase();
  for (const [key, value] of Object.entries(mockAnswers)) {
    if (lowerQuery.includes(key.toLowerCase())) {
      return value;
    }
  }

  return {
    answer: `Based on web research for "${query}", here are the key findings: This is a mock response. Configure SAP_AI_HUB_ENDPOINT and SAP_AUTH_TOKEN to enable real web search via Perplexity AI through SAP Generative AI Hub.`,
    sources: ['https://example.com/mock-source-1', 'https://example.com/mock-source-2'],
  };
}

/**
 * Performs web search using Perplexity AI through SAP Generative AI Hub
 * @param query - The search query
 * @param maxResults - Maximum number of results to return
 * @param modelName - The model to use ('sonar' for quick search, 'sonar-pro' for deep research)
 */
async function performWebSearch(
  query: string, 
  maxResults = 5, 
  modelName: 'sonar' | 'sonar-pro' = 'sonar'
): Promise<WebSearchOutput> {
  try {
    const client = await createPerplexityClient(modelName);

    const response = await client.chat.completions.create({
      model: modelName,
      messages: [
        {
          role: 'user',
          content: query,
        },
      ],
      max_tokens: modelName === 'sonar-pro' ? 2000 : 1000, // More tokens for deep research
      temperature: 0.2,
      return_related_questions: false,
      return_images: false,
    });

    // Extract content - handle both string and array formats
    const messageContent = response.choices[0]?.message?.content;
    let answer = 'No answer available';
    
    if (typeof messageContent === 'string') {
      answer = messageContent;
    } else if (Array.isArray(messageContent)) {
      // Extract text from content chunks
      const textChunks = messageContent
        .filter(chunk => 'text' in chunk)
        .map(chunk => chunk.text);
      answer = textChunks.join('\n');
    }

    const sources = response.citations || [];

    return {
      answer,
      sources: sources.slice(0, maxResults),
    };
  } catch (error) {
    // If SAP AI Core is not configured, fall back to mock
    if (error instanceof Error && 
        (error.message.includes('AICORE_SERVICE_KEY') || 
         error.message.includes('deployment URL'))) {
      console.warn('SAP AI Core not configured, using mock web search');
      return mockWebSearch(query, maxResults);
    }
    throw error;
  }
}

export function registerWebSearchTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'web_search',
    {
      title: 'Web Search Tool',
      description: 'Quick web search using Perplexity Sonar. Get AI-synthesized answers with sources. Use this for straightforward queries.',
      inputSchema: webSearchSchemaShape,
      outputSchema: webSearchResultSchemaShape,
    },
    async ({ query, max_results }: WebSearchInput) => {
      const result = await performWebSearch(query, max_results || 5, 'sonar');

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
        structuredContent: result,
      };
    }
  );
}

export function registerWebResearchTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'web_research',
    {
      title: 'Web Research Tool',
      description: 'Deep web research using Perplexity Sonar Pro. More comprehensive and detailed analysis. Use this for complex research questions that require in-depth investigation.',
      inputSchema: webSearchSchemaShape,
      outputSchema: webSearchResultSchemaShape,
    },
    async ({ query, max_results }: WebSearchInput) => {
      const result = await performWebSearch(query, max_results || 5, 'sonar-pro');

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
        structuredContent: result,
      };
    }
  );
}
