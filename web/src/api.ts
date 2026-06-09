export type SourceType = "url" | "pdf";
export type UrlImportMode = "auto" | "chrome";

export interface MaterialSource {
  id: string;
  material_id: string;
  source_type: SourceType;
  source_uri: string;
  is_primary: boolean;
}

export interface MaterialSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  primary_source: MaterialSource;
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
    }>;
  }>;
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

export function importUrl(url: string, mode: UrlImportMode = "auto"): Promise<MaterialDetail> {
  return request<MaterialDetail>("/api/import/url", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, mode }),
  });
}
