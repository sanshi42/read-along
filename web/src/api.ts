export type SourceType = "url" | "pdf";
export type UrlImportMode = "auto" | "chrome";
export type ImportOutcome = "created" | "reused_source" | "reused_content";

export interface MaterialSource {
  id: string;
  material_id: string;
  source_type: SourceType;
  source_uri: string;
  is_primary: boolean;
}

export interface ReadingProgress {
  material_id: string;
  sentence_id: string;
  sentence_offset_seconds: number;
  playback_rate: number;
  playback_completed: boolean;
  updated_at: string;
}

export interface PlaybackPosition {
  sentence_index: number;
  sentence_count: number;
}

export interface PlaybackTimePosition {
  elapsed_seconds: number;
  total_seconds: number;
  estimated: boolean;
}

export interface MaterialNavigationItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MaterialSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  primary_source: MaterialSource;
  progress: ReadingProgress | null;
  playback_position: PlaybackPosition | null;
  playback_time_position: PlaybackTimePosition | null;
}

export interface MaterialDetail extends MaterialSummary {
  sources: MaterialSource[];
  navigation: {
    first: MaterialNavigationItem | null;
    previous: MaterialNavigationItem | null;
    next: MaterialNavigationItem | null;
    last: MaterialNavigationItem | null;
  };
  paragraphs: Array<{
    id: string;
    index: number;
    text: string;
    source_label: string | null;
    sentences: Array<{
      id: string;
      index: number;
      text: string;
      audio_status: "pending" | "ready" | "failed";
      audio_duration_seconds: number | null;
      error_message: string | null;
    }>;
  }>;
}

export interface MaterialImportResult {
  outcome: ImportOutcome;
  material: MaterialDetail;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // 响应不是 JSON 时保留状态码错误信息
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

async function requestWithoutBody(path: string, options?: RequestInit): Promise<void> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // 响应不是 JSON 时保留状态码错误信息
    }
    throw new Error(message);
  }
}

async function requestAudio(path: string): Promise<number | null> {
  const response = await fetch(path);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // 响应不是 JSON 时保留状态码错误信息
    }
    throw new Error(message);
  }
  await response.arrayBuffer();
  const duration = Number(response.headers.get("X-Read-Along-Audio-Duration-Seconds"));
  return Number.isFinite(duration) && duration >= 0 ? duration : null;
}

export function listMaterials(): Promise<MaterialSummary[]> {
  return request<MaterialSummary[]>("/api/materials");
}

export function getMaterial(materialId: string): Promise<MaterialDetail> {
  return request<MaterialDetail>(`/api/materials/${encodeURIComponent(materialId)}`);
}

export function deleteMaterial(materialId: string): Promise<void> {
  return requestWithoutBody(`/api/materials/${encodeURIComponent(materialId)}`, {
    method: "DELETE",
  });
}

export function clearMaterialAudioCache(materialId: string): Promise<void> {
  return requestWithoutBody(`/api/materials/${encodeURIComponent(materialId)}/audio-cache`, {
    method: "DELETE",
  });
}

export function sentenceAudioUrl(
  materialId: string,
  sentenceId: string,
  reloadToken?: string | null,
): string {
  const path = `/api/materials/${encodeURIComponent(materialId)}/sentences/${encodeURIComponent(sentenceId)}/audio`;
  if (!reloadToken) {
    return path;
  }
  return `${path}?${new URLSearchParams({ reload: reloadToken })}`;
}

export function prepareSentenceAudio(
  materialId: string,
  sentenceId: string,
  reloadToken?: string | null,
): Promise<number | null> {
  return requestAudio(sentenceAudioUrl(materialId, sentenceId, reloadToken));
}

export function saveProgress(
  materialId: string,
  progress: Pick<
    ReadingProgress,
    "sentence_id" | "sentence_offset_seconds" | "playback_rate" | "playback_completed"
  >,
): Promise<ReadingProgress> {
  return request<ReadingProgress>(`/api/materials/${encodeURIComponent(materialId)}/progress`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(progress),
  });
}

export function importUrl(url: string, mode: UrlImportMode = "auto"): Promise<MaterialImportResult> {
  return request<MaterialImportResult>("/api/import/url", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, mode }),
  });
}

export function importPdf(file: File): Promise<MaterialImportResult> {
  const body = new FormData();
  body.append("file", file);
  return request<MaterialImportResult>("/api/import/pdf", {
    method: "POST",
    body,
  });
}
