export type ThemePreference = "system" | "light" | "dark";
export type FontSizePreference = "small" | "standard" | "large";
export type LineHeightPreference = "compact" | "standard" | "relaxed";

export interface ReadingPreferences {
  theme: ThemePreference;
  fontSize: FontSizePreference;
  lineHeight: LineHeightPreference;
}

export const READING_PREFERENCES_STORAGE_KEY = "read-along.reading-preferences.v1";

export const DEFAULT_READING_PREFERENCES: ReadingPreferences = {
  theme: "system",
  fontSize: "standard",
  lineHeight: "standard",
};

const THEMES = new Set<ThemePreference>(["system", "light", "dark"]);
const FONT_SIZES = new Set<FontSizePreference>(["small", "standard", "large"]);
const LINE_HEIGHTS = new Set<LineHeightPreference>(["compact", "standard", "relaxed"]);

export function loadReadingPreferences(): ReadingPreferences {
  try {
    const value = window.localStorage.getItem(READING_PREFERENCES_STORAGE_KEY);
    if (!value) {
      return DEFAULT_READING_PREFERENCES;
    }
    return parseReadingPreferences(JSON.parse(value));
  } catch {
    return DEFAULT_READING_PREFERENCES;
  }
}

export function saveReadingPreferences(preferences: ReadingPreferences): boolean {
  try {
    window.localStorage.setItem(
      READING_PREFERENCES_STORAGE_KEY,
      JSON.stringify(preferences),
    );
    return true;
  } catch {
    return false;
  }
}

export function applyReadingPreferences(preferences: ReadingPreferences): void {
  const root = document.documentElement;
  root.dataset.theme = preferences.theme;
  root.dataset.fontSize = preferences.fontSize;
  root.dataset.lineHeight = preferences.lineHeight;
}

function parseReadingPreferences(value: unknown): ReadingPreferences {
  if (!isRecord(value)) {
    return DEFAULT_READING_PREFERENCES;
  }
  const theme = value.theme;
  const fontSize = value.fontSize;
  const lineHeight = value.lineHeight;
  if (
    typeof theme !== "string" ||
    typeof fontSize !== "string" ||
    typeof lineHeight !== "string" ||
    !THEMES.has(theme as ThemePreference) ||
    !FONT_SIZES.has(fontSize as FontSizePreference) ||
    !LINE_HEIGHTS.has(lineHeight as LineHeightPreference)
  ) {
    return DEFAULT_READING_PREFERENCES;
  }
  return {
    theme: theme as ThemePreference,
    fontSize: fontSize as FontSizePreference,
    lineHeight: lineHeight as LineHeightPreference,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
