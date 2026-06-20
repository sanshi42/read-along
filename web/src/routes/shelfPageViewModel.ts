export function removeMaterialFromList<T extends { id: string }>(
  materials: T[] | null,
  materialId: string,
): T[] | null {
  return materials?.filter((material) => material.id !== materialId) ?? null;
}

export interface FileCandidate {
  name: string;
  type: string;
}

export interface PdfFileSelection<T extends FileCandidate> {
  file: T | null;
  hasFiles: boolean;
}

export function isPdfFile(file: FileCandidate): boolean {
  return file.type.toLowerCase() === "application/pdf" || file.name.trim().toLowerCase().endsWith(".pdf");
}

export function pickPdfFile<T extends FileCandidate>(
  files: ArrayLike<T> | Iterable<T> | null | undefined,
): PdfFileSelection<T> {
  if (!files) {
    return { file: null, hasFiles: false };
  }

  const candidates = Array.from(files as ArrayLike<T> | Iterable<T>);
  return {
    file: candidates.find(isPdfFile) ?? null,
    hasFiles: candidates.length > 0,
  };
}
