#!/usr/bin/env python3
"""
verify_before_push.py — Local gate that must pass BEFORE any git push / fly deploy.

Why this exists:
  On 2026-07-23 the "Wie sie arbeiten" office tab shipped broken: a JS reference
  error (`cv is not defined`) crashed the whole modal IIFE, so `officeInit` was
  never defined and the canvas stayed blank. `node --check` on a naive extract
  passed (it only checks SYNTAX, not runtime scoping). The bug only surfaced
  live, after deploy — exactly the "i refresh and see na ned wirkend" failure
  mode Simeon called out.

This script catches that class of bug locally by actually EXECUTING the rendered
JS in a mock DOM (like Claude Code's last-look-back / hook gate), not just
syntax-checking it. If `showPane`/`officeInit`/etc are undefined after the IIFE
runs, we fail HERE, before push.

Usage:
  python3 scripts/verify_before_push.py
  exit code 0 = safe to push/deploy, non-zero = STOP.
"""
import sys, os, re, subprocess, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTORY = os.path.join(ROOT, "factory")
sys.path.insert(0, FACTORY)

SLUG = "gdpr-guard"  # representative center with a full panel + office tab

# ---------------------------------------------------------------------------
# 1) Python import + render smoke test
# ---------------------------------------------------------------------------
def check_python():
    print("• python import + render smoke...")
    import runtime, catalog
    try:
        _ = runtime.center_card_html(SLUG, "de")
        _ = runtime.center_card_html(SLUG, "en")
        _ = runtime.build_agent_grid()
        _ = runtime.build_antfarm_html("de")
        _ = runtime._firms_grid_body(type("R", (), {"query": {"lang": "de", "q": ""}})())
    except Exception as e:
        return f"runtime render crashed: {e}"
    return None

# ---------------------------------------------------------------------------
# 2) ruff lint
# ---------------------------------------------------------------------------
def check_ruff():
    print("• ruff check (blocking errors only)...")
    # F541/F-string style is non-blocking; we block on real correctness errors.
    # Run with --output-format + filter so stylistic noise doesn't gate deploys.
    r = subprocess.run(["ruff", "check", "--output-format", "concise",
                       os.path.join(FACTORY, "runtime.py")],
                       capture_output=True, text=True)
    lines = [l for l in (r.stdout.splitlines()) if l.strip()]
    # block only on error CODES that indicate real bugs (not F541/F841 style)
    blocking = [l for l in lines if re.search(r"\b(E9|E7|F821|F822|F823)\b", l)]
    if blocking:
        return "ruff real errors:\n" + "\n".join(blocking[:20])
    if lines:
        print(f"  (ruff: {len(lines)} stylistic warnings, non-blocking)")
    return None

# ---------------------------------------------------------------------------
# 3) extract every <script> block from a rendered page and node --check it
# ---------------------------------------------------------------------------
def check_node_syntax(html):
    print("• node --check on every <script> block...")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    for i, b in enumerate(blocks):
        p = f"/tmp/_vbp_block_{i}.js"
        open(p, "w").write(b)
        r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
        if r.returncode != 0:
            return f"block {i} syntax error:\n{r.stderr[-500:]}"
    return None

# ---------------------------------------------------------------------------
# 4) DOM-CONTEXT EXECUTE — the real gate (catches scoping/runtime bugs)
#    Runs each IIFE in a mock DOM; asserts the functions the app depends on
#    are actually defined after the script runs.
# ---------------------------------------------------------------------------
def check_js_runtime(html):
    print("• execute JS in mock DOM (last-look-back gate)...")
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    # which symbols must exist after the office/modal block runs
    required = ["showPane", "officeInit", "pollLive"]
    node_prog = r"""
const fs=require("fs");
const code=fs.readFileSync(process.argv[2],"utf8");
function fakeEl(){return {onclick:null,addEventListener(){},classList:{toggle(){},add(){},remove(){},contains:()=>false},style:{},getContext:()=>ctx2d,width:1200,height:800,getBoundingClientRect:()=>({left:0,top:0,width:1200,height:800}),querySelector:()=>null,querySelectorAll:()=>[]};}
const ctx2d={scale(){},fillRect(){},beginPath(){},arc(){},fill(){},stroke(){},fillText(){},save(){},restore(){},translate(){},rotate(){},clearRect(){},moveTo(){},lineTo(){},rect(){},ellipse(){},measureText:()=>({width:10}),setLineDash(){},roundRect(){}};
global.window={addEventListener(){},devicePixelRatio:1,__cmOfficeCanvas:null};
global.document={getElementById:()=>fakeEl(),querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>fakeEl(),addEventListener(){},body:{appendChild(){}}};
global.localStorage={getItem:()=>""};
global.location={pathname:"/",search:"",hash:""};
global.fetch=()=>Promise.resolve({json:()=>Promise.resolve({}),text:()=>Promise.resolve("")});
global.requestAnimationFrame=()=>{};
global.setTimeout=()=>0;
global.setInterval=()=>0;
global.clearInterval=()=>{};
const __hardTimeout=setTimeout(function(){console.log("ERR:hard-timeout");process.exit(0);},8000);
try{
  const inner=code.replace(/^\(function\(\)\{/,"").replace(/\}\)\(\);\s*$/,"");
  const wrapped="(function(){"+inner+"; return {showPane:typeof showPane, officeInit:typeof officeInit, pollLive:typeof pollLive};})()";
  const res=eval(wrapped);
  clearTimeout(__hardTimeout);
  console.log(JSON.stringify(res));
}catch(e){ clearTimeout(__hardTimeout); console.log("ERR:"+e.message); }
"""
    for i, b in enumerate(blocks):
        p = f"/tmp/_vbp_run_{i}.js"
        open(p, "w").write(b)
        np = "/tmp/_vbp_runner.js"
        open(np, "w").write(node_prog)
        r = subprocess.run(["node", np, p], capture_output=True, text=True, timeout=20)
        out = r.stdout.strip()
        if out.startswith("ERR:"):
            return f"block {i} RUNTIME ERROR: {out[4:]}"
        try:
            syms = json.loads(out)
        except Exception:
            continue  # block without our symbols (e.g. actwave) — skip
        # only enforce the office/modal contract on the block that defines officeInit
        if "officeInit" not in b:
            continue
        for sym in required:
            if syms.get(sym) != "function":
                return f"block {i}: '{sym}' is {syms.get(sym)} (must be function) — IIFE crashed before definition"
    return None

def main():
    print(f"=== verify_before_push ({SLUG}) ===")
    import runtime, catalog
    html = runtime.center_card_html(SLUG, "de")

    fails = []
    for name, fn in [
        ("python", check_python),
        ("ruff", check_ruff),
        ("node-syntax", lambda: check_node_syntax(html)),
        ("js-runtime", lambda: check_js_runtime(html)),
    ]:
        try:
            err = fn()
        except Exception as e:
            fails.append(f"{name}: EXCEPTION {e}")
            continue
        if err:
            fails.append(f"{name}: {err}")
            print(f"  ✗ {name} FAILED")
        else:
            print(f"  ✓ {name} ok")

    print("=" * 40)
    if fails:
        print("GATE FAILED — DO NOT PUSH/DEPLOY:")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("GATE PASSED — safe to push + deploy.")
    sys.exit(0)

if __name__ == "__main__":
    main()
