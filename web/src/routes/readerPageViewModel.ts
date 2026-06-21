export interface RectLike {
  top: number;
  bottom: number;
  height: number;
}

export interface ReaderChromeBounds {
  top: number;
  bottom: number;
}

export interface ReaderChromeBoundsInput {
  viewportHeight: number;
  navBottom: number;
  playerTop: number | null;
  margin: number;
}

export interface ReaderNavContextInput {
  headerBottom: number;
  navBottom: number;
}

export interface ReaderContextProgressInput {
  sentenceIndex: number;
  sentenceCount: number;
  timelinePositionLabel: string;
  timelineTotalLabel: string;
}

export interface ReaderSentenceInteractionInput {
  sentenceIndex: number;
  sentenceCount: number;
  isCurrent: boolean;
  isPlaying: boolean;
}

export interface ReaderSentenceInteraction {
  ariaCurrent?: "location";
  ariaLabel?: string;
  tabIndex?: 0;
}

export type SentencePointerAction = "select" | "play";
export type ZenModeShortcutAction = "toggle" | "exit";

export interface ReaderShortcutInput {
  key: string;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
}

export interface ZenModeShortcutContext {
  zenMode: boolean;
  interactiveTarget: boolean;
}

export function normalizeReadingTitle(title: string): string {
  return title.replace(/\.pdf$/i, "").trim();
}

export function sentencePointerAction(clickCount: number): SentencePointerAction {
  return clickCount >= 2 ? "play" : "select";
}

export function zenModeShortcutAction(
  input: ReaderShortcutInput,
  context: ZenModeShortcutContext,
): ZenModeShortcutAction | null {
  if (input.altKey || input.ctrlKey || input.metaKey) {
    return null;
  }
  if (input.key === "Escape") {
    return context.zenMode ? "exit" : null;
  }
  if (context.interactiveTarget) {
    return null;
  }
  return input.key.toLowerCase() === "z" ? "toggle" : null;
}

export function shouldShowReaderNavContext({
  headerBottom,
  navBottom,
}: ReaderNavContextInput): boolean {
  return headerBottom <= navBottom;
}

export function readerContextProgressLabel({
  sentenceIndex,
  sentenceCount,
  timelinePositionLabel,
  timelineTotalLabel,
}: ReaderContextProgressInput): string {
  const sentenceLabel =
    sentenceIndex >= 0 && sentenceCount > 0
      ? `第 ${sentenceIndex + 1} / ${sentenceCount} 句`
      : sentenceCount > 0
        ? `共 ${sentenceCount} 句`
        : "";
  return [sentenceLabel, timelinePositionLabel || timelineTotalLabel].filter(Boolean).join(" · ");
}

export function readerChromeBoundsForFixedControls({
  viewportHeight,
  navBottom,
  playerTop,
  margin,
}: ReaderChromeBoundsInput): ReaderChromeBounds {
  const safeMargin = Math.max(0, margin);
  const top = Math.min(viewportHeight, Math.max(0, navBottom) + safeMargin);
  const visibleBottom = Math.max(0, viewportHeight - safeMargin);
  const playerAwareBottom =
    playerTop === null ? visibleBottom : Math.max(0, playerTop - safeMargin);
  return {
    top,
    bottom: Math.min(visibleBottom, playerAwareBottom),
  };
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

export function readerSentenceInteraction({
  sentenceIndex,
  sentenceCount,
  isCurrent,
  isPlaying,
}: ReaderSentenceInteractionInput): ReaderSentenceInteraction {
  if (!isCurrent) {
    return {};
  }
  const status = isPlaying ? "正在播放" : "当前句";
  const progress =
    sentenceIndex >= 0 && sentenceCount > 0
      ? `，第 ${sentenceIndex + 1} / ${sentenceCount} 句`
      : "";
  return {
    ariaCurrent: "location",
    ariaLabel: `${status}${progress}。按 Enter 播放或暂停；双击任意句可从该句播放。`,
    tabIndex: 0,
  };
}
