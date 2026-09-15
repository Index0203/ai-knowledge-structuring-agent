export type ThemeId = "instagram" | "ocean" | "mint" | "violet" | "sunset";

export type ThemeDefinition = {
  id: ThemeId;
  label: string;
  /** Colours used for the swatch in the picker. */
  swatch: [string, string, string];
  vars: Record<string, string>;
};

function pageWash(glowA: string, glowB: string, glowC: string, base: [string, string, string]): string {
  return [
    `radial-gradient(circle at 12% 8%, ${glowA}, transparent 42%)`,
    `radial-gradient(circle at 88% 4%, ${glowB}, transparent 46%)`,
    `radial-gradient(circle at 78% 92%, ${glowC}, transparent 46%)`,
    `linear-gradient(135deg, ${base[0]} 0%, ${base[1]} 48%, ${base[2]} 100%)`,
  ].join(", ");
}

export const THEMES: ThemeDefinition[] = [
  {
    id: "instagram",
    label: "紫粉",
    swatch: ["#833AB4", "#E1306C", "#FCAF45"],
    vars: {
      "--brand-1": "#833AB4",
      "--brand-2": "#C13584",
      "--brand-3": "#E1306C",
      "--brand-4": "#F77737",
      "--brand-5": "#FCAF45",
      "--brand-ink": "#833AB4",
      "--brand-soft": "#FBF3FF",
      "--brand-soft-2": "#FFEFF6",
      "--brand-line": "#EFE1F5",
      "--brand-ring": "rgba(225, 48, 108, 0.22)",
      "--brand-ring-soft": "rgba(225, 48, 108, 0.35)",
      "--brand-shadow": "rgba(131, 58, 180, 0.45)",
      "--brand-shadow-strong": "rgba(225, 48, 108, 0.6)",
      "--brand-dots": "#E7D7F3",
      "--brand-edge": "#CFA8E4",
      "--brand-page": pageWash(
        "rgba(131, 58, 180, 0.16)",
        "rgba(225, 48, 108, 0.14)",
        "rgba(252, 175, 69, 0.18)",
        ["#FFF5FA", "#F8F3FF", "#FFF8EF"],
      ),
    },
  },
  {
    id: "ocean",
    label: "海盐蓝",
    swatch: ["#1D4ED8", "#0EA5E9", "#22D3EE"],
    vars: {
      "--brand-1": "#1D4ED8",
      "--brand-2": "#2563EB",
      "--brand-3": "#0EA5E9",
      "--brand-4": "#06B6D4",
      "--brand-5": "#67E8F9",
      "--brand-ink": "#1D4ED8",
      "--brand-soft": "#EEF4FF",
      "--brand-soft-2": "#E8F7FF",
      "--brand-line": "#D8E6FB",
      "--brand-ring": "rgba(37, 99, 235, 0.22)",
      "--brand-ring-soft": "rgba(14, 165, 233, 0.35)",
      "--brand-shadow": "rgba(29, 78, 216, 0.4)",
      "--brand-shadow-strong": "rgba(14, 165, 233, 0.55)",
      "--brand-dots": "#CFE3FA",
      "--brand-edge": "#9CC4F0",
      "--brand-page": pageWash(
        "rgba(37, 99, 235, 0.14)",
        "rgba(14, 165, 233, 0.14)",
        "rgba(34, 211, 238, 0.18)",
        ["#F2F7FF", "#EDF6FF", "#F0FDFF"],
      ),
    },
  },
  {
    id: "mint",
    label: "薄荷绿",
    swatch: ["#0F766E", "#10B981", "#6EE7B7"],
    vars: {
      "--brand-1": "#0F766E",
      "--brand-2": "#059669",
      "--brand-3": "#10B981",
      "--brand-4": "#34D399",
      "--brand-5": "#A7F3D0",
      "--brand-ink": "#0F766E",
      "--brand-soft": "#ECFDF5",
      "--brand-soft-2": "#E6FBF4",
      "--brand-line": "#D2F0E4",
      "--brand-ring": "rgba(16, 185, 129, 0.22)",
      "--brand-ring-soft": "rgba(16, 185, 129, 0.35)",
      "--brand-shadow": "rgba(15, 118, 110, 0.35)",
      "--brand-shadow-strong": "rgba(16, 185, 129, 0.5)",
      "--brand-dots": "#CDEFE0",
      "--brand-edge": "#95DCC2",
      "--brand-page": pageWash(
        "rgba(15, 118, 110, 0.14)",
        "rgba(16, 185, 129, 0.14)",
        "rgba(110, 231, 183, 0.2)",
        ["#F1FBF7", "#ECFDF5", "#F0FDFA"],
      ),
    },
  },
  {
    id: "violet",
    label: "紫罗兰",
    swatch: ["#4C1D95", "#8B5CF6", "#C4B5FD"],
    vars: {
      "--brand-1": "#4C1D95",
      "--brand-2": "#6D28D9",
      "--brand-3": "#8B5CF6",
      "--brand-4": "#A78BFA",
      "--brand-5": "#DDD6FE",
      "--brand-ink": "#6D28D9",
      "--brand-soft": "#F5F1FF",
      "--brand-soft-2": "#EFE9FF",
      "--brand-line": "#E1D8FB",
      "--brand-ring": "rgba(139, 92, 246, 0.22)",
      "--brand-ring-soft": "rgba(139, 92, 246, 0.38)",
      "--brand-shadow": "rgba(76, 29, 149, 0.4)",
      "--brand-shadow-strong": "rgba(139, 92, 246, 0.55)",
      "--brand-dots": "#DCD0FA",
      "--brand-edge": "#C3ABF5",
      "--brand-page": pageWash(
        "rgba(76, 29, 149, 0.14)",
        "rgba(139, 92, 246, 0.14)",
        "rgba(196, 181, 253, 0.22)",
        ["#F7F4FF", "#F3EFFF", "#FBF5FF"],
      ),
    },
  },
  {
    id: "sunset",
    label: "落日橘",
    swatch: ["#C2410C", "#F97316", "#FDE68A"],
    vars: {
      "--brand-1": "#C2410C",
      "--brand-2": "#EA580C",
      "--brand-3": "#F97316",
      "--brand-4": "#FBBF24",
      "--brand-5": "#FDE68A",
      "--brand-ink": "#C2410C",
      "--brand-soft": "#FFF4EC",
      "--brand-soft-2": "#FFF7E6",
      "--brand-line": "#FBE0CB",
      "--brand-ring": "rgba(249, 115, 22, 0.22)",
      "--brand-ring-soft": "rgba(249, 115, 22, 0.38)",
      "--brand-shadow": "rgba(194, 65, 12, 0.38)",
      "--brand-shadow-strong": "rgba(249, 115, 22, 0.5)",
      "--brand-dots": "#F7DDC2",
      "--brand-edge": "#F3C392",
      "--brand-page": pageWash(
        "rgba(194, 65, 12, 0.13)",
        "rgba(249, 115, 22, 0.14)",
        "rgba(253, 230, 138, 0.24)",
        ["#FFF6EE", "#FFF1E4", "#FFFAEF"],
      ),
    },
  },
];

export const DEFAULT_THEME: ThemeId = "instagram";
export const THEME_STORAGE_KEY = "knowledge-agent-theme";

export function themeVars(theme: ThemeId): Record<string, string> {
  return (THEMES.find((item) => item.id === theme) ?? THEMES[0]).vars;
}

function isThemeId(value: string | null): value is ThemeId {
  return THEMES.some((item) => item.id === value);
}

/** The chosen palette survives a reload; storage failures fall back to the default. */
export function readStoredTheme(): ThemeId | null {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeId(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function storeTheme(theme: ThemeId): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Private mode or a blocked storage API: the theme simply is not remembered.
  }
}
