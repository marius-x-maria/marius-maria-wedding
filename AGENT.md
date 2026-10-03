# Agent Briefing — Wedding Site (marius-maria.com)

Read this file at the start of every session. It is the single source of truth for the agent's role, current state, and rules for this project.

---

## Your Role

You maintain and extend the live wedding invitation website for **Marius & Maria**, deployed at **marius-maria.com** via GitHub Pages.

This is a production site with real guests visiting. Every change must be correct before it goes live. Your job is to implement requested features, keep the codebase clean, and never break what already works.

---

## Capability Registry

**Single source of truth for what exists.** Four states: `included` (built, expected to work) · `available` (partial — the note says exactly what is missing) · `absent` (not built; add only on request) · `removed` (deliberately deleted; restore only on request).

**Without a row, a capability is `absent`.** Existing code is not a request — finding a half-built thing does not authorize finishing it.

| Capability | State | Note |
|---|---|---|
| Single-file PWA (`index.html`) | `included` | No build step, no deps beyond Google Fonts |
| Live at marius-maria.com | `included` | GitHub Pages + `CNAME`. **Production — real guests visit** |
| Bilingual EN / RO | `included` | `data-lang` attributes; RO is the default on load. Rule 5 |
| All 11 content sections | `included` | Hero, Story, Big Day, RSVP, Gallery, Library, Gift, Stay, Beauty, Moldova, Nightlife — see reference below |
| RSVP form → Google Sheets | `included` | 5 fields via Apps Script. Fire-and-forget `no-cors` |
| Guest photo upload → Drive | `available` | Live since 2026-07-29. **Known ceiling: 6 photos ≈ 70–80 s** — Apps Script's 30-execution cap. Upgrade path documented, deliberately not taken |
| Guest **video** upload → Drive | `included` | Always supported — dedicated `accept="video/*"` picker, bilingual labels, 🎬 preview tile. 25 MB cap ≈ 20–25 s of 1080p or ~4 s of 4K |
| Upload verification | `included` | `doGet ?check=` re-polls rather than re-uploading; only a manual tap retries. **Window now scales with file size** (12 s floor → 5 min ceiling). Fixed 2026-10-03: the old flat ~8 s window declared large videos failed mid-flight, and the retry minted a new `storedName` so both copies landed |
| Oversized-file handling | `included` | Rejected **per file** with a ⚠ badge and a reason, not per batch. The rest of the selection still uploads |
| Upload accessibility | `absent` | Known defects, deferred 2026-10-03: both pickers are `display:none` so keyboard-unreachable; retry badge is touch-only; no `aria-live` on status; remove button 22 px vs 44 px minimum; `Remove` label English-only in RO mode |
| Upload progress detail | `absent` | The ⬆ badge is static for the whole read + POST + verify window. No byte-level progress — on a long video it reads as frozen |
| Responsive layout | `included` | 7 breakpoints: 1600/1280/900/700/680/420/360 + landscape phone. Test at 375 and 680 per Rule 7 |
| Reduced-motion support | `included` | All animation disabled under `prefers-reduced-motion` |
| PWA install | `available` | `manifest.json` + apple-touch-icon only. **No service worker** — not installable offline |
| Open Graph / Twitter Card | `included` | `og-invite.png` 1200×630 |
| Scroll reveal, hero zoom, botanical dividers | `included` | IntersectionObserver; 12 s hero zoom; film-grain overlay |
| Transport smart-links | `included` | OS detection → Bolt, Letz, Yandex Go |
| Gift / bank transfer section | `included` | EN only, hidden in RO. IBAN is public by design — accepted risk AR-01 |
| Brand tokens in `:root` | `included` | Olive palette. Rule 6 — never introduce a colour without asking |
| Service worker / offline | `absent` | Would make it a true offline PWA |
| RSVP dashboard | `absent` | Read Sheets → headcount, dietary, transport, zeama counts |
| Guest list manager | `absent` | Track who has and has not responded |
| Countdown widget | `absent` | To 30 July 2026 |
| Seating plan | `absent` | `tools/preview-seats.mjs` exists but **has never been runnable** — no Node on this machine, and no workflow references it |
| Guest-name hashing | `absent` | `tools/hash-guests.mjs` — same: never runnable, unreferenced |
| RSVP deadline enforcement | `absent` | Auto-hide or disable after 1 July 2026. Rule 9 |
| Post-wedding thank-you state | `absent` | Keys off 30 July 2026. Rule 10 |
| Book list | `absent` | Wishlist for the Library section |
| Dark theme | `absent` | Not requested. Visual checks shoot light only |
| Asset budget | `available` | `web_predeploy.py` flags two images over the 200 KB guideline on a live site: `hero.jpg` 443.6 KB and `story-main.jpg` 262.3 KB. Both load on first paint. Not fixed — recompressing production images is a separate, visual decision |
| Automated tests | `available` | One suite: `tools/test_gallery_upload.py` — 12 behaviour tests over the upload path, `fetch` fully stubbed so nothing reaches Drive. Run it before touching the gallery. Nothing else on the site is covered |
| Build tooling / bundler | `removed` | Deliberate — Rule 4. Restoring it is a Tier-1 decision, see [[web-tier-upgrade]] |
| Backend / database | `removed` | Deliberate — Apps Script replaces it. Tier 2 otherwise |
| Accounts / auth | `absent` | Tier 2. Guests need no account by design |
| Payments | `absent` | Tier 2. The Gift section is a bank transfer, not a checkout |
| Infrastructure as code | `absent` | Not adopted — no Terraform in this framework |

**Director:** Vibe Coder Agent · **Tier:** 0 (zero-build static) · **Engaged subagents:** [[ui_specialist]], [[web_deploy_specialist]], plus [[frontend_engineer]] for any non-trivial slice.

> **Two orphan tools.** `tools/hash-guests.mjs` and `tools/preview-seats.mjs` are Node ES modules. Node has never been installed on this machine, so neither has ever run, and no workflow references them. [[it_department]] has flagged this four sessions running. They are recorded `absent` above rather than quietly left as if they worked. Making them real is a Tier-1 ask — see [[web-tier-upgrade]].

---

## How It Works (reference)

The site is a **single-file PWA** (`index.html`) — all HTML, CSS, and JavaScript in one file, no build step, no dependencies beyond Google Fonts.

### Sections (in order)

| Section ID | Name | What it does |
|---|---|---|
| `#home` | Hero | Full-viewport photo (hero.jpg), couple names, date/time/venue pills, CTA to RSVP |
| `#story` | Our Story | Two-column: narrative text left, overlapping story photos right |
| `#bigday` | The Big Day | Olive-green section — venue name (linked to Google Maps), schedule timeline, dress code |
| `#rsvp` | RSVP | Live form — submits to Google Apps Script → Google Sheets |
| `#gallery` | Photos (guest upload) | Upload form live now (made live 2026-07-29, not gated to ceremony start); uploads go to Google Drive via a dedicated Apps Script |
| `#library` | Library / Book Gift | Suggests books instead of flowers; describes the book stand at the reception |
| `#gift` | Wedding Gift | Bank transfer details (EN only — hidden in RO mode) |
| `#stay` | Stay & Travel | Accommodation recommendations (Airbnb + 2 hotels), transport apps |
| `#beauty` | Beauty & Grooming | 4 ladies' salons, 3 barbers — all Google Maps linked |
| `#moldova` | Discover Moldova | Wine experiences (3 wineries), must-visit sights (3 landmarks) |
| `#nightlife` | Bars & Restaurants | 3 bars, 4 restaurants — all Google Maps linked |
| Footer | — | Names + date + venue, olive background |

### Key Features

- **Bilingual (EN / RO)** — language toggle top-right; default is Romanian (`setLang('ro')` on load); all text uses `data-lang="en"` / `data-lang="ro"` attributes
- **PWA** — manifest.json + apple-touch-icon; installable on iOS/Android
- **Responsive** — breakpoints at 1600px, 1280px, 900px, 700px, 680px, 420px, 360px; landscape phone handling; reduced-motion support
- **Nav** — transparent over hero, frosts to ivory on scroll; hamburger + full-screen drawer on mobile
- **RSVP form** — 5 fields: names, attendance (yes/no), dietary info, transport preference, post-wedding zeama lunch; submits via `fetch` to Google Apps Script (no-cors fire-and-forget); shows success message on submit
- **Scroll reveal** — IntersectionObserver adds `.visible` class to `.reveal` elements
- **Hero animation** — slow zoom (12s infinite) on hero.jpg; film-grain SVG overlay
- **Botanical SVG dividers** — hand-drawn olive-branch motif between sections
- **Open Graph / Twitter Card** — og-invite.png (1200x630), full social sharing metadata
- **Gift section** — EN only (hidden for RO speakers via JS); Revolut IBAN `LT63 3250 0304 0910 6958`, BIC `REVOLT21`
- **Transport smart-links** — detects iOS/Android/desktop to open Bolt, Letz, Yandex Go in correct store
- **Guest photo upload** — `#gallery` section, live now (made live 2026-07-29 by decision, not gated to ceremony start), a file picker that uploads directly to Google Drive via a second Apps Script (no Google account needed on the guest's side); see [[../workflows/add-photo-gallery]]

### RSVP Backend

- **Google Apps Script URL**: `https://script.google.com/macros/s/AKfycbyKws6Tqx5AcghaKd5k79AyrkLgTphuep8xLTDheXgY2vwmyvVmu8w969NoZRmGPc_E/exec`
- Payload fields: `name`, `attendance`, `dietary`, `transport`, `zeama`
- No auth, no error handling on the response (opaque no-cors); success is always shown

### Gallery Upload Backend

- **Target Drive folder**: `1JGyjT6_a6XeIq_ZfKbkiOnLOLbDiqPIK`
- **Google Apps Script URL**: `https://script.google.com/macros/s/AKfycbx0_SLQaOk9pJIK8JsyZg71_LYXK1-Hrdn6pgthCoEu6J-CLmeS7w1AZDlWlwotIEklxQ/exec` — deployed 2026-07-28, redesigned + redeployed + verified end-to-end 2026-07-29 — see [[../workflows/add-photo-gallery]]
- Deliberately a **separate deployment** from the RSVP script (Rule #2 — never touch the working RSVP backend)
- `doPost` payload: `storedName` (client-generated, collision-proof), `mimeType`, `data` (base64) — fire-and-forget `no-cors`, same limitation as RSVP (Apps Script can't set CORS response headers)
- `doGet`: `?check=<storedName>` — real, reliably-readable verification (plain GET, no preflight) that a specific upload actually landed in Drive; a failed check re-polls (never re-uploads), only a guest's manual tap on a failed badge triggers a real retry
- Client uploads **2 files concurrently per device** (`GALLERY_CONCURRENCY`) to balance throughput against Apps Script's 30-simultaneous-execution cap shared across every guest uploading at once
- **Known performance ceiling** — 6 photos take ~70-80s; researched 2026-07-29 whether a faster architecture exists (direct-to-Drive resumable upload, serverless proxy). Decided to keep Apps Script as-is given the wedding's timing — see [[../workflows/add-photo-gallery]] "Performance ceiling" section for the full reasoning and the documented future upgrade path if ever revisited

---

---

## Key Files

| File | Purpose |
|---|---|
| `index.html` | The entire site — HTML, CSS, JS, all in one file |
| `manifest.json` | PWA manifest — name, icons, theme colour, start URL |
| `CNAME` | GitHub Pages custom domain — `marius-maria.com` |
| `images/hero.jpg` | Full-viewport hero photo |
| `images/story-main.jpg` | Our Story section — main photo |
| `images/story-accent.jpg` | Our Story section — accent/overlay photo |
| `images/icon-192.png` | PWA home-screen icon |
| `images/icon-512.png` | PWA splash icon |
| `images/og-invite.png` | Social share image (1200×630) |
| `images/og-envelope.png` | Alternate OG image (unused in current meta) |
| `knowledge-base/wedding_spec.md` | Single source of truth for all wedding facts |
| `skills/README.md` | Map of project-specific skills |
| `workflows/README.md` | Map of project-specific workflows |

---

## Design Spec

### Colour Palette

| Token | Hex | Usage |
|---|---|---|
| `--ivory` | `#f9f6ef` | Page background, nav frosted bg |
| `--parchment` | `#f2ece0` | Beauty, Stay, Gift section backgrounds |
| `--olive` | `#6b7a4e` | Primary brand colour, buttons, accents |
| `--olive-dk` | `#6b8055` | Hover states, links |
| `--olive-lt` | `#a8b890` | Decorative lines, secondary accents |
| `--sage` | `#8a9b7a` | Mid-tone accent |
| `--sage-lt` | `#d4ddc8` | Light accent, Big Day section text |
| `--text` | `#2e2e1e` | Body text |
| `--text-mid` | `#5a5a3a` | Secondary body text |
| `--text-lt` | `#8a8a6a` | Tertiary / placeholder text |
| `--border` | `rgba(107,122,78,0.25)` | Card borders |
| `--bigday-bg` | `#7a8f5a` | Big Day and Footer background |
| `--rsvp-bg` | `#eef2e6` | RSVP section background |

### Typography

| Font | Weights | Usage |
|---|---|---|
| Cormorant Garamond | 300, 400, 500, 600 (+ italics) | Headings, names, decorative serif |
| Jost | 200, 300, 400 | Body text, labels, nav, buttons |

### Motion & Style

- Minimal animation: hero zoom (12s), fadeUp on page load, scroll-reveal
- Reduced-motion: all animation disabled via `@media (prefers-reduced-motion: reduce)`
- Film-grain SVG overlay at 4.5% opacity on hero
- Botanical SVG dividers (olive branch motif, olive palette)
- Border-radius: none — all cards and buttons are sharp-cornered
- Image filters: `saturate(0.87) contrast(1.05)` — desaturated, filmic look

### Tone

Elegant, restrained, romantic. Serif for emotion, sans-serif for information. No emoji in design elements (used only in content labels like section icons). Bilingual throughout.

---

## Rules

1. **Never break the live site** — this is production; test every change locally before deploying
2. **Never modify the RSVP backend** without verifying the Google Apps Script still works — responses are real guest data
3. **Never hardcode secrets** — the Apps Script URL is public by design; any future credentials go in environment files, not in `index.html`
4. **No build tools** — keep the single-file architecture; if complexity grows, propose before adding bundlers/frameworks
5. **Preserve bilingual integrity** — every new text element needs both `data-lang="en"` and `data-lang="ro"` variants
6. **Respect the palette** — use only the CSS custom properties defined in `:root`; never introduce new colours without asking
7. **Mobile-first** — test all additions at 375px and 680px (the two most critical breakpoints)
8. **Commit only clean changes** — never commit with console.log, commented-out blocks, or debug code left in
9. **RSVP deadline is 1 July 2026** — any feature touching the form must account for this
10. **Wedding date is 30 July 2026** — countdowns, auto-hide logic, and post-wedding states must key off this date

---

## Shared Skills

See `C:\New life\skills\README.md` for shared skills available across all projects.

Project-specific skills (if any) live in `skills/README.md` in this directory.

---

## Session Optimizer

**Run at the end of every session where work was approved.**

Invoke `[[session_optimizer]]` from `C:\New life\skills\`:
1. Update this AGENT.md — move completed items from pending to built
2. Update `knowledge-base/wedding_spec.md` with any new facts discovered
3. Tighten skills and workflows with constraints learned this session
4. Commit: `chore: session optimizer — update state, prune memory, tighten skills/workflows`
