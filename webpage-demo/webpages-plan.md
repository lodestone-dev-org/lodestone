# Third Space — Design Document

## 1. Overview

**Project:** Third Space
**Platform:** Web (GitHub Pages)
**Current weekly theme:** Harvest

Third Space is a themed website and server-preview experience. Core identity stays consistent; visual design (background, colors, typography, decorations, UI styling, animations, server-preview atmosphere) changes weekly.

## 2. Goals

* Immersive weekly experience, showcasing the Third Space server.
* Server front-end preview, GitHub link, download link.
* Team showcase, theme archive, accessibility support.
* Weekly theme updates should stay simple.

## 3. Site Structure

text
Home (Weekly Theme, GitHub, Download, Server Preview)
Server Preview
Themes
Team
Accessibility


## 4. Homepage

Immediately shows: branding, current theme, short description, GitHub button, Download button, Server Preview button.

Buttons need hover/focus/active states, keyboard support, and a reduced-motion alternative.

## 5. Server Preview

Demonstrates the server's front end without requiring full server access — nav, dashboard, server status, user profile, content cards, notifications, settings. Clearly label it as demonstration-only.

Each theme controls background, colors, typography, buttons, cards, borders, shadows, decorations, animations, and server-preview styling. Layout/identity stays consistent.

### Current theme — Harvest

Warm autumn/harvest concept (leaves, grain, organic shapes, warm lighting). Gentle floating/particle animation, subtle transitions — must not hurt readability.

## 6. Theme Page

Current theme: name, week/date, description, preview, palette, inspiration, UI examples.
Archive: each past theme keeps a screenshot, description, date, palette, notes.

## 7. Team Page

Per member: name, role, avatar, short bio, links, contributions. Uses the current weekly theme.

## 8. Accessibility

**Reduced motion** — toggle to disable transitions/parallax/decorations; respect prefers-reduced-motion`.
**High contrast** — readable text, visible controls/focus states, no color-only info.
**Font size** — Normal / Large / Extra Large.
**Keyboard** — full navigation, logical tab order, visible focus.
**Screen readers** — semantic HTML (`header`, `nav`, `main`, `section`, `article`, `footer`), meaningful labels/alt text.

## 9. Responsive & Performance

Support desktop/laptop/tablet/mobile. Mobile priority order: branding → theme → main message → Enter Server → GitHub → Download → navigation. Reduce animation on smaller devices.

Keep it lightweight: compressed/modern-format images, lazy-load non-critical assets, minimal JS/fonts, fallbacks for missing assets.



json
{
  "name": "Harvest",
  "week": "01",
  "description": "A warm seasonal theme inspired by autumn and harvest.",
  "colors": { "background": "", "surface": "", "primary": "", "secondary": "", "accent": "", "text": "", "muted": "", "border": "" },
  "background": "",
  "animation": "gentle",
  "decorations": []
}
```

## 11. Weekly Update Process

1. Choose theme (name, concept, mood, inspiration, palette).
2. Create assets (background, decorations, icons, illustrations, preview).
3. Configure `theme.json`.
4. Test (desktop, mobile, contrast, keyboard, screen reader, reduced motion, performance, buttons, preview).
5. Publish to GitHub.
6. Archive the previous theme.

12. Definition of Done

Homepage + Harvest theme implemented
*Theme system + archive structure implemented
GitHub / Download / Server Preview buttons work
Theme Page + Team Page work
Accessibility: reduced motion, high contrast, font scaling, keyboard nav
Mobile + desktop layouts, focus states
GitHub Pages deployment works
*README explains theme creation
