export function removeMaterialFromList<T extends { id: string }>(
  materials: T[] | null,
  materialId: string,
): T[] | null {
  return materials?.filter((material) => material.id !== materialId) ?? null;
}
