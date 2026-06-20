import type { PlaybackMode } from "./routes/playbackMode";

export const PLAYBACK_MODE_STORAGE_KEY = "read-along.playback-mode.v1";

const DEFAULT_PLAYBACK_MODE: PlaybackMode = "sequential";
const PLAYBACK_MODES = new Set<PlaybackMode>(["repeat_one", "sequential", "repeat_list"]);

function isPlaybackMode(value: unknown): value is PlaybackMode {
  return typeof value === "string" && PLAYBACK_MODES.has(value as PlaybackMode);
}

export function loadPlaybackModePreference(): PlaybackMode {
  try {
    const value = window.localStorage.getItem(PLAYBACK_MODE_STORAGE_KEY);
    if (!value) {
      return DEFAULT_PLAYBACK_MODE;
    }
    const parsed = JSON.parse(value) as unknown;
    return isPlaybackMode(parsed) ? parsed : DEFAULT_PLAYBACK_MODE;
  } catch {
    return DEFAULT_PLAYBACK_MODE;
  }
}

export function savePlaybackModePreference(mode: PlaybackMode): boolean {
  try {
    window.localStorage.setItem(PLAYBACK_MODE_STORAGE_KEY, JSON.stringify(mode));
    return true;
  } catch {
    return false;
  }
}
