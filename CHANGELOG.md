# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Major UI overhaul: themed light/dark stylesheets, masthead with wordmark
  and persona pill, Lucide-based monochrome toolbar icons.
- Sidebar restructured into a single scrollable column of clear sections
  (Pacing / Speed / Newlines / Behavior / Compliance / Macros) — replaces
  the previous Setup/Safety tabs and nested QGroupBoxes.
- Custom `ChevronSplitterHandle` with click-to-toggle and animated collapse;
  scrollbars thinned and made semi-transparent so they no longer compete
  with the splitter handle.
- Inline metric strip replacing the old Stats tab; output preview is a
  collapsible toggle.

### Added
- Visible spinbox arrows, white checkmark inside checked boxes, cyan dot
  inside selected radios (rendered from SVG to PNG at first theme load).
- README, requirements.txt, comprehensive `.gitignore`.
- GitHub Actions: macOS + Windows release builds on tag push, syntax/import
  CI on PRs.

### Fixed
- AI-paste artifact sanitization at high WPM ([5b7230f]).
- Shift-state races during fast typing ([5b7230f]).

## [3.3] — 2025-04-21

Last commit before the UI overhaul. See git history for details.
