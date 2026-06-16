export interface RectLike {
  top: number;
  bottom: number;
  height: number;
}

export interface ReaderChromeBounds {
  top: number;
  bottom: number;
}

export interface ReaderNavContextInput {
  headerBottom: number;
  navBottom: number;
}

export type SentencePointerAction = "select" | "play";

export function normalizeReadingTitle(title: string): string {
  return title.replace(/\.pdf$/i, "").trim();
}

export function sentencePointerAction(clickCount: number): SentencePointerAction {
  return clickCount >= 2 ? "play" : "select";
}

export function shouldShowReaderNavContext({
  headerBottom,
  navBottom,
}: ReaderNavContextInput): boolean {
  return headerBottom <= navBottom;
}

export function isRectFullyVisibleWithinReaderChrome(
  rect: RectLike,
  bounds: ReaderChromeBounds,
): boolean {
  return rect.top >= bounds.top && rect.bottom <= bounds.bottom;
}

export function scrollTargetForRectWithinReaderChrome(
  rect: RectLike,
  scrollY: number,
  bounds: ReaderChromeBounds,
): number {
  const readableHeight = Math.max(0, bounds.bottom - bounds.top);
  const offsetWithinBand =
    rect.height <= readableHeight ? Math.max(0, (readableHeight - rect.height) / 2) : 0;
  return Math.max(0, scrollY + rect.top - bounds.top - offsetWithinBand);
}
