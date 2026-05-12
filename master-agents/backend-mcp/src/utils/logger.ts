type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const currentLogLevel: LogLevel = (process.env.LOG_LEVEL?.toLowerCase() as LogLevel) || 'info';
const currentLogLevelValue = LOG_LEVELS[currentLogLevel] ?? LOG_LEVELS.info;

function shouldLog(level: LogLevel): boolean {
  return LOG_LEVELS[level] >= currentLogLevelValue;
}

function formatTimestamp(): string {
  return new Date().toISOString();
}

function truncate(value: unknown, maxLength = 200): string {
  const str = typeof value === 'string' ? value : JSON.stringify(value);
  if (str.length <= maxLength) {
    return str;
  }
  return `${str.slice(0, maxLength)}...`;
}

export function logToolExecution(
  toolName: string,
  input: unknown,
  output: unknown,
  level: LogLevel = 'info',
): void {
  if (!shouldLog(level)) {
    return;
  }

  const timestamp = formatTimestamp();
  const inputStr = truncate(input);
  const outputStr = truncate(output);

  console.log(`[${timestamp}] [${level.toUpperCase()}] Tool: ${toolName} | Input: ${inputStr} | Output: ${outputStr}`);
}

export function logError(message: string, error?: unknown): void {
  if (!shouldLog('error')) {
    return;
  }

  const timestamp = formatTimestamp();
  const errorStr = error instanceof Error ? error.message : String(error);
  console.error(`[${timestamp}] [ERROR] ${message} | ${errorStr}`);
}

export function logInfo(message: string): void {
  if (!shouldLog('info')) {
    return;
  }

  const timestamp = formatTimestamp();
  console.log(`[${timestamp}] [INFO] ${message}`);
}

export function logDebug(message: string): void {
  if (!shouldLog('debug')) {
    return;
  }

  const timestamp = formatTimestamp();
  console.log(`[${timestamp}] [DEBUG] ${message}`);
}
