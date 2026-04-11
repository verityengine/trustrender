# Fonts

Fonts are trust infrastructure. Output determinism depends on controlling font availability.

## Precedence

1. Explicit `font_paths` from caller (searched first)
2. Bundled fonts directory (searched second)
3. System fonts (Typst default, always available)

## Bundled fonts

TrustRender ships Inter (Regular, Bold, Italic, BoldItalic) as TTF files. All example templates use Inter. Bundled fonts are the deterministic baseline.

## Silent fallback

Typst silently falls back when a requested font is unavailable. The PDF is valid but may use the wrong font. No error is raised at render time.

**Detection before render:**
- `preflight()` parses font declarations from templates and checks against configured font paths
- `trustrender doctor` reports declared vs. found fonts
- Bundled templates missing bundled fonts (Inter) produce a preflight **error**
- Custom templates missing fonts produce a preflight **warning** (may be a system font)

**Detection after render:**
- Baseline drift detection catches font substitution via embedded font comparison

**If you care about deterministic output, rely on bundled or explicitly supplied fonts. Do not rely on system font availability.**

## Custom fonts

| Method | Usage |
|--------|-------|
| Python API | `render(..., font_paths=["/path/to/fonts"])` |
| CLI | `--font-path /path/to/fonts` (repeatable) |
| Env var | `TRUSTRENDER_FONT_PATH=/path/to/fonts` |
| Docker | Mount a volume and set `TRUSTRENDER_FONT_PATH` |
