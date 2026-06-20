export type PlaybackMode = "repeat_one" | "sequential" | "repeat_list";

export interface PlaybackModeNavigation {
  currentId: string;
  previousId: string | null;
  nextId: string | null;
  firstId: string | null;
  lastId: string | null;
}

export interface PlaybackModeTarget {
  materialId: string;
  autoplay: boolean;
}

export const DEFAULT_PLAYBACK_MODE: PlaybackMode = "sequential";

const PLAYBACK_MODES = new Set<PlaybackMode>(["repeat_one", "sequential", "repeat_list"]);

export function isPlaybackMode(value: unknown): value is PlaybackMode {
  return typeof value === "string" && PLAYBACK_MODES.has(value as PlaybackMode);
}

export function playbackModeLabel(mode: PlaybackMode): string {
  switch (mode) {
    case "repeat_one":
      return "单曲循环";
    case "sequential":
      return "顺序播放";
    case "repeat_list":
      return "列表循环";
  }
}

export function playbackModeTargetForNaturalEnd(
  mode: PlaybackMode,
  navigation: PlaybackModeNavigation,
): PlaybackModeTarget | null {
  if (mode === "repeat_one") {
    return { materialId: navigation.currentId, autoplay: true };
  }
  if (navigation.nextId) {
    return { materialId: navigation.nextId, autoplay: true };
  }
  if (mode === "repeat_list" && navigation.firstId) {
    return { materialId: navigation.firstId, autoplay: true };
  }
  return null;
}

export function playbackModeTargetForPrevious(
  mode: PlaybackMode,
  navigation: PlaybackModeNavigation,
): PlaybackModeTarget | null {
  if (navigation.previousId) {
    return { materialId: navigation.previousId, autoplay: false };
  }
  if (mode === "repeat_list" && navigation.lastId) {
    return { materialId: navigation.lastId, autoplay: false };
  }
  return null;
}

export function playbackModeTargetForNext(
  mode: PlaybackMode,
  navigation: PlaybackModeNavigation,
): PlaybackModeTarget | null {
  if (navigation.nextId) {
    return { materialId: navigation.nextId, autoplay: false };
  }
  if (mode === "repeat_list" && navigation.firstId) {
    return { materialId: navigation.firstId, autoplay: false };
  }
  return null;
}
