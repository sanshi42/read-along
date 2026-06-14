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
  playback_rate: number;
  playback_completed: boolean;
  updated_at: string;
}

export interface PlaybackPosition {
  sentence_index: number;
  sentence_count: number;
}

export interface MaterialSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  primary_source: MaterialSource;
  progress: ReadingProgress | null;
  playback_position: PlaybackPosition | null;
}

export interface MaterialDetail extends MaterialSummary {
  sources: MaterialSource[];
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

export function listMaterials(): Promise<MaterialSummary[]> {
  return request<MaterialSummary[]>("/api/materials");
}

export function getMaterial(materialId: string): Promise<MaterialDetail> {
  return request<MaterialDetail>(`/api/materials/${encodeURIComponent(materialId)}`);
}

export function sentenceAudioUrl(materialId: string, sentenceId: string): string {
  return `/api/materials/${encodeURIComponent(materialId)}/sentences/${encodeURIComponent(sentenceId)}/audio`;
}

export function saveProgress(
  materialId: string,
  progress: Pick<ReadingProgress, "sentence_id" | "playback_rate" | "playback_completed">,
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
