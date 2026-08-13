// simcapture.mjs — capture MP4 B-roll of a traffic-sim baked replay.
//
// Drives headless Chrome over the DevTools protocol (node ≥22 global
// WebSocket + fetch, no npm deps — same pattern as traffic-sim's
// viz/scripts/screenshot.mjs), screenshots the replay on a wall-clock
// loop, and assembles true real-time CFR H.264 with the ffmpeg concat
// demuxer. Under --use-angle=swiftshader each Page.captureScreenshot
// takes a VARIABLE 100–300 ms, so every frame records its own timestamp
// and gets its own concat duration — never assume a fixed capture rate.
//
// The viz's own ?bare=1 mode hides all UI chrome (.hud panels, theme
// toggle, loading overlay, maplibre controls — app.html) and is appended
// automatically; hidden panels still update, so the tool reads the sim
// tick from the hidden #status HUD and seeks by driving the hidden
// #replay slider (baked-mode seeks only exist through the panel's
// in-page fetch stub — there is no ?tick= URL param).
//
// GOTCHA (baked.ts BAKED_VEHICLE_GATE_ZOOM): vehicles only render at
// zoom ≥ 13 — always deep-link ?center=lng,lat&zoom=N in the URL.
//
// Usage:
//   node simcapture.mjs --url <replay-url> --out clip.mp4
//     [--duration 10] [--size 1080x1920] [--start-tick N] [--speed 1|2|4|8]
//     [--camera path.json | '[{...}]'] — drone keyframes: [{at, duration,
//       center?, zoom?, bearing?, pitch?, ease?: "ease"|"fly"|"jump"}, ...]
//       (seconds from record start; fired on window.__viz.map)
//     [--crf 18] [--settle 1.5] [--format png|jpeg] [--keep-frames] [--gpu]
//
// Requires: chrome/chromium (env CHROME overrides), ffmpeg (resolution
// mirrors ff.py: VIDKIT_FFMPEG env -> homebrew ffmpeg@7 -> PATH), and
// the bake served with Content-Encoding: br (traffic-sim
// scripts/serve-baked.py — plain http.server breaks the .br chunks).

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { delimiter, join } from "node:path";
import { tmpdir } from "node:os";
import { setTimeout as sleep } from "node:timers/promises";

// --- args -------------------------------------------------------------------

function parseArgs(argv) {
  const a = {
    url: null,
    out: null,
    duration: 10,
    size: "1080x1920",
    startTick: null,
    speed: null,
    camera: null,
    fps: 30,
    crf: 18,
    settle: 1.5,
    format: "png",
    keepFrames: false,
    gpu: false,
    timeout: 120,
  };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const next = () => argv[++i];
    if (k === "--url") a.url = next();
    else if (k === "--out") a.out = next();
    else if (k === "--duration") a.duration = Number(next());
    else if (k === "--size") a.size = next();
    else if (k === "--start-tick") a.startTick = Number(next());
    else if (k === "--speed") a.speed = Number(next());
    else if (k === "--camera") a.camera = next();
    else if (k === "--fps") a.fps = Number(next());
    else if (k === "--crf") a.crf = Number(next());
    else if (k === "--settle") a.settle = Number(next());
    else if (k === "--format") a.format = next();
    else if (k === "--keep-frames") a.keepFrames = true;
    else if (k === "--gpu") a.gpu = true;
    else if (k === "--timeout") a.timeout = Number(next());
    else throw new Error(`unknown arg: ${k}`);
  }
  if (!a.url || !a.out) {
    console.error(
      "usage: node simcapture.mjs --url <replay-url> --out clip.mp4\n" +
        "  [--duration 10] [--size 1080x1920] [--start-tick N] [--fps 30]\n" +
        "  [--crf 18] [--settle 1.5] [--format png|jpeg] [--keep-frames] [--timeout 120]",
    );
    process.exit(2);
  }
  const m = /^(\d+)x(\d+)$/.exec(a.size);
  if (!m) throw new Error(`--size must be WxH, got ${a.size}`);
  a.width = Number(m[1]);
  a.height = Number(m[2]);
  if (a.width % 2 || a.height % 2) throw new Error("--size must be even (yuv420p)");
  if (a.format !== "png" && a.format !== "jpeg") throw new Error("--format must be png|jpeg");
  if (a.speed !== null && ![1, 2, 4, 8].includes(a.speed))
    throw new Error("--speed must be one of 1|2|4|8 (replaypanel SPEEDS)");
  if (a.camera !== null) {
    const src = a.camera.trim().startsWith("[") ? a.camera : readFileSync(a.camera, "utf8");
    a.moves = JSON.parse(src);
    if (!Array.isArray(a.moves)) throw new Error("--camera must be a JSON array of keyframes");
    a.moves.sort((x, y) => (x.at ?? 0) - (y.at ?? 0));
    for (const m of a.moves) {
      if (m.zoom !== undefined && m.zoom < 13)
        console.warn(`[warn] camera keyframe at t=${m.at ?? 0}s zooms to ${m.zoom} < 13 — baked vehicles will vanish`);
    }
  } else {
    a.moves = [];
  }
  return a;
}

// --- binary resolution ------------------------------------------------------

const HOMEBREW_FFMPEG7 = "/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg";

function which(name) {
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    if (dir && existsSync(join(dir, name))) return join(dir, name);
  }
  return null;
}

function resolveFfmpeg() {
  if (process.env.VIDKIT_FFMPEG) return process.env.VIDKIT_FFMPEG;
  if (existsSync(HOMEBREW_FFMPEG7)) return HOMEBREW_FFMPEG7;
  const found = which("ffmpeg");
  if (found) return found;
  throw new Error("ffmpeg not found: set VIDKIT_FFMPEG or put ffmpeg on PATH");
}

function resolveChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const c of ["google-chrome", "chromium", "chromium-browser", "chrome"]) {
    const found = which(c);
    if (found) return found;
  }
  throw new Error("chrome/chromium not found: set CHROME or put one on PATH");
}

// --- main -------------------------------------------------------------------

const args = parseArgs(process.argv.slice(2));
const FFMPEG = resolveFfmpeg();
const CHROME = resolveChrome();

// ?bare=1: the viz's own clean-canvas mode (hides every .hud panel, the
// theme toggle, the loading overlay and maplibre controls). Panels keep
// updating while hidden — the tick reads and slider seek below rely on it.
const url = new URL(args.url);
if (!url.searchParams.has("bare")) url.searchParams.set("bare", "1");
if (url.searchParams.has("bake")) {
  const zoom = Number(url.searchParams.get("zoom") ?? "NaN");
  if (!url.searchParams.has("center") || !(zoom >= 13)) {
    console.warn(
      "[warn] baked vehicles only render at zoom >= 13 " +
        "(BAKED_VEHICLE_GATE_ZOOM) — deep-link ?center=lng,lat&zoom=13+ " +
        "or the clip will show an empty network",
    );
  }
}

const profileDir = mkdtempSync(join(tmpdir(), "simcapture-profile-"));
const framesDir = mkdtempSync(join(tmpdir(), "simcapture-frames-"));

const chrome = spawn(
  CHROME,
  [
    "--headless",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    // swiftshader renders anywhere but rasters a 1080x1920 frame with
    // thousands of vehicles in ~600 ms (~1.5 fps captured); --gpu drops
    // it for hardware GL where available (~real GPU: several × faster).
    ...(args.gpu
      ? ["--use-angle=gl", "--ignore-gpu-blocklist"]
      : ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]),
    "--hide-scrollbars",
    "--remote-debugging-port=0", // real port lands in DevToolsActivePort
    `--user-data-dir=${profileDir}`,
    `--window-size=${args.width},${args.height}`,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let chromeErr = "";
chrome.stderr.on("data", (d) => (chromeErr += d));

let ok = false;
try {
  // Port 0 avoids collisions with other harnesses; Chrome writes the
  // chosen port to <profile>/DevToolsActivePort once the endpoint is up.
  let port = 0;
  for (let i = 0; i < 60 && !port; i++) {
    try {
      port = Number(readFileSync(join(profileDir, "DevToolsActivePort"), "utf8").split("\n")[0]);
    } catch {
      await sleep(250);
    }
  }
  if (!port) throw new Error("devtools endpoint never came up\n" + chromeErr.slice(-2000));
  const target = await (
    await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })
  ).json();

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  };
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const id = ++seq;
      pending.set(id, (m) => (m.error ? rej(new Error(`${method}: ${m.error.message}`)) : res(m)));
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, returnByValue: true });
    if (r.result?.exceptionDetails) {
      throw new Error(`page eval failed: ${JSON.stringify(r.result.exceptionDetails).slice(0, 400)}`);
    }
    return r.result?.result?.value;
  };

  await send("Page.enable");
  await send("Runtime.enable");
  // Pin the viewport to the exact requested size regardless of how the
  // window manager treats --window-size.
  await send("Emulation.setDeviceMetricsOverride", {
    width: args.width,
    height: args.height,
    deviceScaleFactor: 1,
    mobile: false,
  });
  console.log(`[nav] ${url}`);
  await send("Page.navigate", { url: String(url) });

  // The hidden #status HUD keeps rendering "tick N  vehicles M" in bare
  // mode — it is the in-page truth for both liveness and seek landing.
  const hud = async () => {
    const text = await evaluate("document.getElementById('status')?.textContent ?? ''");
    const m = /tick (\d+)\s+vehicles (\d+)/.exec(text ?? "");
    return m ? { tick: Number(m[1]), vehicles: Number(m[2]), text } : { tick: null, vehicles: null, text };
  };
  const waitFor = async (what, timeoutMs, cond) => {
    const t0 = Date.now();
    for (;;) {
      const v = await cond();
      if (v) return v;
      if (Date.now() - t0 > timeoutMs) throw new Error(`timed out waiting for ${what} (${timeoutMs} ms)`);
      await sleep(500);
    }
  };

  await waitFor("first replay frame (tick > 0)", args.timeout * 1000, async () => {
    const h = await hud();
    return h.tick !== null && h.tick > 0 ? h : null;
  });
  console.log(`[live] ${(await hud()).text.split("\n")[1]}`);

  if (args.startTick !== null || args.speed !== null) {
    // The replay panel (slider max = endTick, value in ticks; speed
    // buttons "1×".."8×") POSTs its controls to the bake shim's in-page
    // fetch stub. The panel builds after its first 1 s status poll.
    await waitFor("replay panel slider", 30_000, () =>
      evaluate(
        "(() => { const s = document.querySelector('#replay input[type=range]');" +
          " return !!s && Number(s.max) > 0 && !s.disabled; })()",
      ),
    );
  }
  if (args.speed !== null) {
    const res = await evaluate(
      "(() => { const b = [...document.querySelectorAll('#replay .rp-speed')]" +
        `.find((x) => x.textContent === '${args.speed}\\u00d7');` +
        " if (!b) return 'no-button'; b.click(); return 'ok'; })()",
    );
    if (res !== "ok") throw new Error(`speed ${args.speed}x: ${res}`);
    console.log(`[speed] ${args.speed}x`);
  }
  if (args.startTick !== null) {
    const res = await evaluate(
      "(() => { const s = document.querySelector('#replay input[type=range]');" +
        ` s.value = String(${args.startTick}); s.dispatchEvent(new Event('change')); return s.max; })()`,
    );
    console.log(`[seek] tick ${args.startTick} requested (slider max ${res})`);
    // Seeks floor to the bake stride and the interpolation buffer refills
    // after the reset — wait for the HUD to land at/after the target with
    // vehicles streaming again.
    await waitFor(`HUD to reach tick ${args.startTick}`, 60_000, async () => {
      const h = await hud();
      return h.tick !== null && h.tick >= args.startTick - 5 && h.vehicles > 0 ? h : null;
    });
    console.log(`[seek] landed: ${(await hud()).text.split("\n")[1]}`);
  }

  if (args.settle > 0) await sleep(args.settle * 1000);

  // Capture loop: wall-clock timed. Screenshot latency under swiftshader
  // is variable, so each frame records the moment its capture was
  // REQUESTED (the compositor grabs the then-current frame); the deltas
  // become per-frame concat durations below.
  const startHud = await hud();
  const stamps = [];
  const ext = args.format === "png" ? "png" : "jpg";
  let moveIdx = 0;
  const t0 = Date.now();
  console.log(`[rec] ${args.duration}s @ ${args.width}x${args.height} (${args.format}) …`);
  while (Date.now() - t0 < args.duration * 1000) {
    const t = Date.now() - t0;
    // Drone camera: keyframes fire as maplibre eases on the map handle the
    // viz exposes for headless harnesses (main.ts window.__viz). Eases run
    // on wall-clock rAF, so the timestamped frames sample them correctly.
    // Keyframe: {at, duration, center?, zoom?, bearing?, pitch?, ease?}
    // (seconds; ease: "ease" default | "fly" | "jump"). Don't overlap
    // moves — a new ease interrupts the running one.
    while (moveIdx < args.moves.length && t / 1000 >= (args.moves[moveIdx].at ?? 0)) {
      const m = args.moves[moveIdx++];
      const fn = m.ease === "jump" ? "jumpTo" : m.ease === "fly" ? "flyTo" : "easeTo";
      const opts = {};
      for (const k of ["center", "zoom", "bearing", "pitch"]) if (m[k] !== undefined) opts[k] = m[k];
      if (fn !== "jumpTo") opts.duration = (m.duration ?? 2) * 1000;
      // Wrapped: map methods return the Map itself, which returnByValue
      // cannot serialize ("Object reference chain is too long").
      await evaluate(`(() => { window.__viz.map.${fn}(${JSON.stringify(opts)}); return "ok"; })()`);
      console.log(`[cam] t=${(t / 1000).toFixed(1)}s ${fn} ${JSON.stringify(opts)}`);
    }
    const shot = await send("Page.captureScreenshot", {
      format: args.format,
      ...(args.format === "jpeg" ? { quality: 90 } : {}),
    });
    const name = `f${String(stamps.length).padStart(6, "0")}.${ext}`;
    writeFileSync(join(framesDir, name), Buffer.from(shot.result.data, "base64"));
    stamps.push({ t, name });
  }
  const endHud = await hud();
  ws.close();
  chrome.kill("SIGKILL");

  if (stamps.length < 2) throw new Error(`only ${stamps.length} frame(s) captured — nothing to encode`);
  const capFps = (stamps.length / args.duration).toFixed(1);
  console.log(
    `[rec] ${stamps.length} frames in ${args.duration}s (~${capFps} fps captured), ` +
      `HUD tick ${startHud.tick} -> ${endHud.tick}, vehicles ${startHud.vehicles} -> ${endHud.vehicles}`,
  );
  if (endHud.tick !== null && startHud.tick !== null && endHud.tick <= startHud.tick) {
    console.warn("[warn] HUD tick did not advance during capture — the clip may be a freeze-frame");
  }

  // Concat demuxer with per-frame durations = true real time; the last
  // frame is repeated after its duration (demuxer convention: the final
  // entry's duration is only honored with a trailing file line).
  const lines = ["ffconcat version 1.0"];
  for (let i = 0; i < stamps.length; i++) {
    const dur =
      i + 1 < stamps.length
        ? (stamps[i + 1].t - stamps[i].t) / 1000
        : Math.max(1 / args.fps, args.duration - stamps[i].t / 1000);
    lines.push(`file ${stamps[i].name}`, `duration ${dur.toFixed(4)}`);
  }
  lines.push(`file ${stamps[stamps.length - 1].name}`);
  const listPath = join(framesDir, "list.ffconcat");
  writeFileSync(listPath, lines.join("\n") + "\n");

  const ff = spawn(
    FFMPEG,
    [
      "-y",
      "-f", "concat",
      "-i", listPath,
      "-fps_mode", "cfr",
      "-r", String(args.fps),
      "-c:v", "libx264",
      "-crf", String(args.crf),
      "-preset", "medium",
      "-pix_fmt", "yuv420p",
      "-movflags", "+faststart",
      args.out,
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  let ffErr = "";
  ff.stderr.on("data", (d) => (ffErr += d));
  const code = await new Promise((res) => ff.on("close", res));
  if (code !== 0) throw new Error(`ffmpeg exited ${code}\n` + ffErr.slice(-2000));
  console.log(`[out] ${args.out}`);
  ok = true;
} finally {
  chrome.kill("SIGKILL");
  rmSync(profileDir, { recursive: true, force: true });
  if (args.keepFrames || !ok) console.log(`[frames] kept at ${framesDir}`);
  else rmSync(framesDir, { recursive: true, force: true });
}
