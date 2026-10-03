---
name: add-photo-gallery
description: Full SOP for the guest photo-upload gallery — Apps Script deployment steps and source, reveal-gating logic, sequential upload queue with real verification, and how to redeploy if it ever needs rebuilding
tags: [workflow, wedding, gallery, apps-script]
---

# Workflow: Photo Gallery (Guest Upload)

## Objective

Let any wedding guest upload phone photos/videos into a Google Drive folder, from a plain upload button on the site itself — no Google account or sign-in required on the guest's side. Built 2026-07-28, gated to reveal at ceremony start (14:30, 30 July 2026). Redesigned 2026-07-29 for multi-select + real per-file confirmation, expecting ~50 guests uploading around the same time.

## Why this design (not a shared Drive folder link)

Native Google Drive folder-sharing and Google Forms' file-upload question both **require the uploader to sign in with a Google account** — this is a hard Google-side requirement, not a setting. Given the guest list likely includes people without Google accounts, that fails accessibility. Instead, this reuses the same pattern already proven for RSVP: a Google Apps Script Web App, deployed under Marius's own authorization, receives the file from the site's own upload button and writes it into Drive on the guest's behalf. The guest never sees a Google login screen.

**This is a separate, independent Apps Script deployment from the RSVP one** — per `AGENT.md` Rule #2, the working RSVP backend is never touched by this feature.

## Scale considerations (added 2026-07-29, updated same day)

Google Apps Script Web Apps cap out at **30 simultaneous executions per deploying account, 1,000 per script** (2026 quotas, same for free and paid accounts) — this is a real, hittable ceiling with ~50 guests uploading in a burst right after the ceremony. Current design:

1. **Client processes up to 2 files at a time per device** (`runGalleryQueuePool` in `index.html`, `GALLERY_CONCURRENCY = 2`) — a guest picking 10 photos does not fire 10 simultaneous requests, but does run 2 concurrently rather than strictly 1-at-a-time (see the Performance Ceiling section below for why it's not higher). **Drops to 1 automatically when any queued file exceeds `GALLERY_LARGE_FILE_BYTES` (5MB)** — two large uploads share one uplink and each halves the other's throughput.
2. **Real per-file verification** (`doGet` check) — a failed check re-polls, it never silently re-uploads. Only an explicit guest tap on a failed (✕) badge triggers an actual new upload attempt. **The polling window is deadline-driven and scales with file size** (`galleryVerifyBudgetMs`): 12s floor, 5-minute ceiling, with an escalating 2→10s interval. See "Verification window" below.

## Performance ceiling (researched 2026-07-29)

Real-world test: 6 photos took ~70-80 seconds even after the concurrency/polling tuning above — this prompted researching whether a fundamentally faster architecture exists before spending more time tuning parameters. Two things were investigated and are worth knowing before attempting this again:

**A cleaner "direct-to-Drive" upload was considered and ruled out.** The idea: have the Apps Script initiate a Drive API resumable-upload session and hand the browser only the session URI, letting the browser PUT bytes straight to Google — bypassing Apps Script as a relay entirely, and (in theory) getting synchronous success confirmation instead of the polling-based verification this feature currently uses. This pattern genuinely works for **Google Cloud Storage** (Google's own docs confirm a bare session URI is a valid, anonymous, write-only credential there) — but **not for Google Drive**. The only real reference implementation for Drive (tanaikech's `ResumableUploadForGoogleDrive_js`) requires handing the browser the site owner's live OAuth **bearer token** on every request, not just a URI. That would mean every guest's browser holds a working credential for Marius's Google account for the life of the token (~1 hour) — inspectable via devtools, usable for anything that token's scope permits, not just uploading one file. **This is a real security regression from the current design and was rejected for that reason**, not attempted.

**Apps Script's latency is a known ceiling, not a misconfiguration.** Multi-second-per-file latency for `doPost` (base64 decode + `DriveApp.createFile`) is widely reported as expected for this specific mechanism — Apps Script has real cold-start overhead, and base64 itself inflates payload size ~33%. Production tools that solve "anonymous upload to my cloud storage" at speed (wedding-photo-sharing apps, general upload widgets) almost universally use S3-compatible object storage (S3, Cloudflare R2) with presigned upload URLs — a mechanism Drive doesn't offer for anonymous writers, which is exactly why this project ended up with the Apps Script relay workaround in the first place.

**If this needs to be meaningfully faster in the future** (e.g. reusing this feature for another event, with more runway than "the day before the wedding"): the architecturally correct upgrade is a small serverless proxy function (e.g. a Cloudflare Worker, free tier) holding a real Drive API **service account** — never exposed to the browser — that mediates the upload and returns a synchronous, CORS-clean JSON response. This would eliminate both the base64 overhead and the polling/verification mechanism entirely, and is more secure than the resumable-token approach above (credentials never leave the server side). It requires: a Cloudflare account, a Google Cloud service account with access to the target Drive folder, and writing/deploying/testing a new function — real new infrastructure, not a tuning change. **Decided against attempting this before the wedding** given the risk of untested new infrastructure breaking on the day; documented here so a future, non-time-pressured session doesn't have to re-research this from scratch.

## Inputs required

- Target Drive folder ID: `1JGyjT6_a6XeIq_ZfKbkiOnLOLbDiqPIK`
- A Google account to own the Apps Script deployment (same one that owns the target Drive folder)

## Steps

### 1. Create and deploy the Apps Script (manual, one-time — or redeploy if updating)

1. Go to [script.google.com](https://script.google.com) → New Project (or open the existing gallery project if redeploying)
2. Replace the code with:

```js
var FOLDER_ID = '1JGyjT6_a6XeIq_ZfKbkiOnLOLbDiqPIK';
var MAX_BYTES = 26214400; // ~25MB safety cap, matches the client-side guard in index.html

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var bytes = Utilities.base64Decode(body.data);
    if (bytes.length > MAX_BYTES) {
      return ContentService.createTextOutput(JSON.stringify({ok:false, error:'too_large'}))
        .setMimeType(ContentService.MimeType.JSON);
    }
    // storedName is generated client-side (timestamp + random token + sanitized
    // original name) and used verbatim — this is also the exact key the doGet
    // verification check below looks up, so it must not be re-stamped here.
    var blob = Utilities.newBlob(bytes, body.mimeType, body.storedName);
    DriveApp.getFolderById(FOLDER_ID).createFile(blob);
    return ContentService.createTextOutput(JSON.stringify({ok:true}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ok:false, error:String(err)}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Verification endpoint — plain GET, so it's always a "simple request" (no CORS
// preflight) and its JSON response is reliably readable by a real fetch(), unlike
// the doPost response above. The client polls this once per file after uploading
// to get real success/failure instead of trusting the opaque no-cors POST.
function doGet(e) {
  var name = e.parameter.check;
  if (!name) {
    return ContentService.createTextOutput(JSON.stringify({ok:false, error:'missing_check_param'}))
      .setMimeType(ContentService.MimeType.JSON);
  }
  var files = DriveApp.getFolderById(FOLDER_ID).getFilesByName(name);
  return ContentService.createTextOutput(JSON.stringify({exists: files.hasNext()}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

3. Deploy → **Manage deployments** → edit the existing deployment → **New version** (keeps the same `/exec` URL) — or **New deployment** → Web app if this is the very first deploy
4. Execute as: **Me** · Who has access: **Anyone**
5. Authorize the script when Google prompts (it needs Drive access to write/read the folder)
6. Confirm the `.../exec` URL — should be unchanged if you edited the existing deployment rather than creating a new one

**Gotcha hit during the first deploy (2026-07-28):** the access dropdown has two similar options — "Anyone" (truly public, no sign-in) vs "Anyone with a Google account" (still requires sign-in). The first attempt landed on the wrong one and returned a 403 "you need access" page for anonymous requests. Fix: **Manage deployments** → edit → re-confirm "Anyone" → deploy a new version.

### 2. `index.html` already points at the existing URL

`var GALLERY_SCRIPT_URL = ...` near the bottom of the `<script>` block doesn't need to change when redeploying via "New version" (same URL). Only update it if a brand-new deployment produces a different URL.

**The upload fetch must use `mode: 'no-cors'` for the POST**, same as RSVP — Apps Script's `ContentService` cannot set CORS response headers, so a real fetch still can't reliably read that response even avoiding the preflight. Real confirmation comes from the separate `doGet` verification check instead (a plain GET, no preflight, reliably readable).

### 3. Verify before trusting it

Do **not** rely on `curl` to test the POST path — Google's Apps Script exec URLs relay through a `302` redirect to a `script.googleusercontent.com` echo endpoint, and curl's redirect/POST-body handling for that specific relay is inconsistent and gives misleading errors (411, 405) even when the upload actually succeeded server-side. The `doGet` verification endpoint is a plain GET and tests fine with curl directly: `curl "<GALLERY_SCRIPT_URL>?check=<exact-stored-name>"` → `{"exists":true}` or `{"exists":false}`.

For the full upload flow, test with a real browser: pick files on the actual live site, watch the per-item badges go ⏳ → ⬆ → ✓ (or ✕ after 2 retries), and cross-check the Drive folder.

Also check drive.google.com storage settings for free space beforehand — free accounts share 15GB across Gmail/Drive/Photos; dozens of guests uploading multiple photos/videos can add up fast.

**Verified 2026-07-28** (v1, single-file): real browser test uploaded a file that landed correctly in the target Drive folder.

## How the reveal gating works

`initGalleryReveal()` in `index.html` compares `now` against a threshold `Date`. Before that moment: the `#gallery-teaser` block shows (with a day- or hour-precision countdown). At/after that moment: `#gallery-teaser` hides and `#gallery-active` (the real upload form) shows. Same technique as `initRSVPDeadline()` — plain `Date` math, `style.display` toggling, called once at script-load time.

To change the reveal moment, edit the single `new Date(...)` line — nothing else needs to change.

**Decision, 2026-07-29: gallery made live immediately, not gated to ceremony start.** The threshold is set to `2026-07-27T00:00:00` (already in the past), so the upload form is active now rather than waiting for 14:30 on 30 July — Marius's explicit call, not a leftover test artifact. The `#gallery-teaser` countdown code is still in place (harmless, just never reached while the threshold stays in the past) in case the reveal-later behavior is wanted for a future event reusing this feature.

## Upload pipeline (v2, 2026-07-29)

1. Guest taps "Choose Photos" / "Choose Videos" (`multiple` attribute — can pick several at once, and tap again to add more before confirming)
2. Each pick adds a thumbnail to the preview grid (image thumb via `createObjectURL`, or a 🎬 icon + filename for video) with a ✕ remove button
3. Guest taps "Upload N items" — this locks in the current pending set (further removes are disabled once queued)
4. `runGalleryQueuePool` runs up to `GALLERY_CONCURRENCY` files at once (1 when anything is large): read as base64 → POST (no-cors, fire-and-forget) → first verification check at 2s → GET check → badge updates to ✓, or re-checks until the deadline
5. **The file is uploaded exactly once per call.** Verification failures re-CHECK, never re-upload. There is no automatic retry of the upload itself
6. A file whose verification deadline expires gets a ✕ badge that is tappable to manually retry, independent of the rest of the batch. Manual retry has no attempt cap
7. Succeeded thumbnails auto-clear ~1.8s after the whole batch finishes; failed ones stay until retried

## Verification window (rewritten 2026-10-03)

The POST is never awaited — `no-cors` gives nothing readable back — so the verification clock starts when the request is **initiated**, not when it completes. The window must therefore outlast the *transfer*, not just Drive's search-index lag.

The old window was flat: first check at 2s, three more at 2s ≈ **8 seconds for every file**. Correct for a 3MB photo. Badly wrong for a 25MB video, which can spend minutes on a phone uplink. The guest saw ✕ while the upload was still in flight, tapped retry, and the retry minted a fresh `storedName` — so the original could not be de-duplicated against it and **both copies landed in Drive**.

Now deadline-driven, scaled by file size (`galleryVerifyBudgetMs`):

| Constant | Value | Why |
|---|---|---|
| `GALLERY_ASSUMED_UPLINK_BPS` | 100 KB/s | Deliberately pessimistic for 4G / venue wifi |
| `GALLERY_BASE64_OVERHEAD` | 1.37 | base64 inflation (~4/3) plus the JSON envelope |
| `GALLERY_VERIFY_MIN_MS` | 12 000 | Floor — Drive index lag on a small file |
| `GALLERY_VERIFY_MAX_MS` | 300 000 | Ceiling — after 5 minutes it really has failed |
| poll interval | 2s → 10s, escalating | Keeps a long wait to ~35 checks, not 150, against the shared 30-execution cap |

Measured budgets: 100KB → 14s · 3MB → 75s · 25MB → 300s (capped).

**Erring generous is deliberate.** Success still reports the moment the file appears; only *failure* is reported later. A slow ✓ costs patience; a premature ✕ costs a duplicate video.

The constants are tuned against an **assumed** uplink, not a measured one — no real video upload has ever been timed on this site. If genuine failures start taking too long to surface, raise `GALLERY_ASSUMED_UPLINK_BPS`.

## Regression test — run before touching the gallery

```bash
python "C:\New life\wedding\tools\test_gallery_upload.py"
```

12 behaviour tests through real Chromium against the real `index.html`. **`fetch` is stubbed entirely** — no network, no Apps Script call, nothing written to Drive — so it is safe to run as often as you like. It covers: the budget curve and its floor/ceiling, the escalating poll interval, a slow upload reporting ✓ instead of a false ✕, the file being POSTed exactly once (the duplicate-video regression), per-file oversize rejection with the rest of the batch still uploading, oversized files staying removable, and concurrency dropping to 1 for large files.

Exit 0 = pass. Written against the 2026-10-03 fix; if it fails, the upload path has regressed.

## Expected output

Real, verified per-file success/failure — not optimistic. A guest who uploads 10 photos sees each one individually confirmed, or flagged once its verification deadline expires.

## Edge cases

- **File too large** (>25MB): rejected **per file**, not per batch — the oversized item gets its own ⚠ badge and a "too large" tooltip, stays removable, and every other file in the selection uploads normally. Backstopped server-side in the Apps Script in case the client check is ever bypassed. For scale: 25MB is ~20–25s of 1080p or ~4s of 4K, so for video this is the common case
- **Transient Apps Script concurrency rejection** (30-simultaneous-execution cap hit by other guests uploading at the same time): the verification window usually outlasts it, so the file is confirmed late rather than falsely failed
- **Verification deadline expires**: flagged with a ✕ badge on that specific thumbnail, tappable to retry manually — does not block or fail the rest of the batch
- **FileReader fails to read the local file** (rare — corrupt file, permissions): counted the same as a failed upload for that item, same retry/flag behavior
- **Guest revisits after uploading**: nothing prevents uploading more later — each file gets its own collision-proof name (timestamp + random token), no dedup needed
- **Drive folder runs out of space**: uploads will fail verification (file won't exist) and get flagged to the guest via the normal failed-badge path — no silent failure anymore, unlike v1
