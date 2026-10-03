#!/usr/bin/env python3
"""Behaviour test for the wedding gallery upload fix.

Stubs fetch entirely: no network, no Drive write, nothing leaves the browser.
Proves the three fixes without touching production.
"""
import sys, tempfile, pathlib, os
from playwright.sync_api import sync_playwright

PAGE = pathlib.Path(r"C:\New life\wedding\index.html").resolve().as_uri()
passed, failed = [], []

def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

def make_file(path, mb):
    with open(path, "wb") as f:
        f.write(b"\0" * int(mb * 1024 * 1024))
    return path

STUB = """(delayMs) => {
  window.__posts = [];
  window.__t0 = Date.now();
  window.fetch = function(url, opts) {
    if (opts && opts.method === 'POST') {
      window.__posts.push(JSON.parse(opts.body).storedName);
      return new Promise(function(){});          // never settles — mimics no-cors in flight
    }
    var exists = (Date.now() - window.__t0) > delayMs;   // Drive "sees" it only after delayMs
    return Promise.resolve({ json: function(){ return Promise.resolve({ exists: exists }); } });
  };
}"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    tmp = tempfile.mkdtemp()

    # ---- Test 1: budget scales with size, and is bounded -------------------
    page = browser.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(PAGE, wait_until="load")
    page.wait_for_timeout(400)
    check("page loads with no JS error", not errs, "; ".join(errs[:2]))

    b3 = page.evaluate("galleryVerifyBudgetMs({size: 3*1024*1024})")
    b25 = page.evaluate("galleryVerifyBudgetMs({size: 25*1024*1024})")
    b_small = page.evaluate("galleryVerifyBudgetMs({size: 100*1024})")
    check("3MB budget beats the old 8s window", b3 > 8000, f"{b3/1000:.0f}s")
    check("25MB budget is far larger", b25 > b3 * 3, f"{b25/1000:.0f}s vs {b3/1000:.0f}s")
    check("budget is capped at 5 min", b25 <= 300000, f"{b25/1000:.0f}s")
    check("tiny file clears the 12s floor and stays short",
          12000 <= b_small < 20000, f"{b_small}ms")
    delays = page.evaluate("[0,1,2,3,10].map(galleryPollDelayMs)")
    check("poll interval escalates and caps at 10s", delays == [2000, 3500, 5000, 6500, 10000], str(delays))

    # ---- Test 2: slow upload no longer reports a false failure ------------
    page2 = browser.new_page()
    page2.goto(PAGE, wait_until="load")
    page2.evaluate(STUB, 15000)          # Drive only confirms after 15s — old code gave up at 8s
    f3 = make_file(os.path.join(tmp, "clip.jpg"), 3)
    page2.set_input_files("#galleryPhotoInput", f3)
    page2.wait_for_timeout(300)
    page2.evaluate("confirmGalleryUpload()")
    page2.wait_for_function(
        "() => galleryPendingFiles.length === 0 || galleryPendingFiles[0].status === 'done' "
        "|| galleryPendingFiles[0].status === 'failed'", timeout=60000)
    status = page2.evaluate("galleryPendingFiles.length ? galleryPendingFiles[0].status : 'done'")
    posts = page2.evaluate("window.__posts.length")
    check("slow upload reports success, not a false failure", status == "done", f"status={status}")
    check("file was uploaded exactly once (no duplicate)", posts == 1, f"{posts} POSTs")

    # ---- Test 3: one oversized file no longer blocks the batch ------------
    page3 = browser.new_page()
    page3.goto(PAGE, wait_until="load")
    page3.evaluate(STUB, 0)              # confirms immediately
    big = make_file(os.path.join(tmp, "big.jpg"), 26)
    ok = make_file(os.path.join(tmp, "ok.jpg"), 1)
    page3.set_input_files("#galleryPhotoInput", [big, ok])
    page3.wait_for_timeout(300)
    page3.evaluate("confirmGalleryUpload()")
    page3.wait_for_timeout(2500)
    states = page3.evaluate("galleryPendingFiles.map(i => i.status)")
    posts3 = page3.evaluate("window.__posts.length")
    check("oversized file marked individually, not batch-blocked", "toolarge" in states, str(states))
    check("the valid file still uploaded", posts3 == 1, f"{posts3} POSTs, states={states}")
    check("oversized file is removable", page3.evaluate(
        "(() => { var n = galleryPendingFiles.length;"
        " var i = galleryPendingFiles.findIndex(x => x.status === 'toolarge');"
        " removeGalleryFile(i); return galleryPendingFiles.length === n - 1; })()"))

    # ---- Test 4: concurrency drops to 1 when a large file is queued -------
    page4 = browser.new_page()
    page4.goto(PAGE, wait_until="load")
    page4.evaluate(STUB, 99000)          # nothing ever confirms, so we can count in-flight
    files = [make_file(os.path.join(tmp, f"big{i}.jpg"), 6) for i in range(3)]
    page4.set_input_files("#galleryPhotoInput", files)
    page4.wait_for_timeout(300)
    page4.evaluate("confirmGalleryUpload()")
    page4.wait_for_timeout(2500)
    inflight = page4.evaluate("window.__posts.length")
    check("large files upload one at a time", inflight == 1, f"{inflight} concurrent POSTs")

    browser.close()

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
