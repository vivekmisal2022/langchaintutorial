import { EventEmitter } from 'events';
import { randomUUID } from 'crypto';

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type JobStage =
  | 'queued'
  | 'parsing'
  | 'chunking'
  | 'embedding'
  | 'storing'
  | 'completed'
  | 'failed';

export interface JobState {
  jobId: string;
  filename: string;
  tenantId?: string;
  status: JobStatus;
  stage: JobStage;
  totalChunks: number;
  processedChunks: number;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  error?: string;
  documentId?: string;
  message?: string;
}

export interface JobUpdate {
  status?: JobStatus;
  stage?: JobStage;
  totalChunks?: number;
  processedChunks?: number;
  error?: string;
  documentId?: string;
  message?: string;
}

const jobs = new Map<string, JobState>();
const jobEvents = new EventEmitter();

// Allow many listeners (one per client per job)
jobEvents.setMaxListeners(0);

export function createJob(params: { filename: string; tenantId?: string }): JobState {
  const job: JobState = {
    jobId: randomUUID(),
    filename: params.filename,
    tenantId: params.tenantId,
    status: 'queued',
    stage: 'queued',
    totalChunks: 0,
    processedChunks: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  jobs.set(job.jobId, job);
  jobEvents.emit(job.jobId, job);
  return job;
}

export function getJob(jobId: string): JobState | undefined {
  return jobs.get(jobId);
}

export function updateJob(jobId: string, update: JobUpdate): JobState | undefined {
  const current = jobs.get(jobId);
  if (!current) {
    return undefined;
  }

  const next: JobState = {
    ...current,
    ...update,
    totalChunks: update.totalChunks ?? current.totalChunks,
    processedChunks: update.processedChunks ?? current.processedChunks,
    stage: update.stage ?? current.stage,
    status: update.status ?? current.status,
    error: update.error ?? current.error,
    documentId: update.documentId ?? current.documentId,
    message: update.message ?? current.message,
    updatedAt: new Date().toISOString(),
  };

  if (next.status === 'completed' || next.status === 'failed') {
    next.completedAt = next.completedAt ?? new Date().toISOString();
  }

  jobs.set(jobId, next);
  jobEvents.emit(jobId, next);
  return next;
}

export function subscribeToJob(jobId: string, listener: (state: JobState) => void): () => void {
  jobEvents.on(jobId, listener);
  return () => {
    jobEvents.off(jobId, listener);
  };
}

export function listJobs(): JobState[] {
  return Array.from(jobs.values());
}
