#!/usr/bin/env python3
"""
llb_call.py — thin stdio client for RFI-IRFOS `moe-llb-mcp` (Last Look Back v1.5).

We DO NOT roll our own safety logic. This just drives the installed `moe-llb`
crate (crates.io: moe-llb-1.5.0) over its stdio MCP channel, so every
filesystem mutation and pre-push check goes through RFI-IRFOS's own
transaction protocol (Gate 1 blacklist/traversal -> Snapshot -> IOCC Gate 2
-> Commit/Rollback).

Usage:
  python3 scripts/llb_call.py validate <abs_path> <CREATE|OVERWRITE|DELETE|CHMOD> [goal] [justification]
  python3 scripts/llb_call.py check    <abs_path> [command]
  python3 scripts/llb_call.py classify <abs_path> <operation>
  python3 scripts/llb_call.py write    <abs_path> <content_file> [CREATE|OVERWRITE] [goal] [justification]

Exit code 0 = LLB allowed (+1), non-zero = veto/error (STOP).
"""
import sys, json, subprocess

MCP_BIN = "/home/eri-irfos/.cargo/bin/moe-llb-mcp"

def _rpc(tool, args):
    init = {"jsonrpc":"2.0","id":1,"method":"initialize",
            "params":{"protocolVersion":"2025-03-26","capabilities":{},
                      "clientInfo":{"name":"llb_call","version":"1.0"}}}
    call = {"jsonrpc":"2.0","id":2,"method":"tools/call",
            "params":{"name":tool,"arguments":args}}
    inp = json.dumps(init)+"\n"+json.dumps(call)+"\n"
    p = subprocess.run([MCP_BIN], input=inp, capture_output=True, text=True, timeout=30)
    # parse the tools/call response (last JSON object on stdout)
    out = p.stdout.strip().splitlines()
    for line in reversed(out):
        try:
            msg = json.loads(line)
            if msg.get("id") == 2:
                return msg
        except Exception:
            continue
    return {"error": p.stderr[-500:] or "no response"}

def _decision(msg):
    """Return (code, text) where code: +1 allow, 0 hold, -1 veto."""
    if "error" in msg:
        return -1, "ERROR: " + str(msg["error"])
    res = msg.get("result", {})
    # moe-llb returns structured content; surface it
    content = res.get("content", [])
    text = ""
    for c in content:
        if c.get("type") == "text":
            text += c.get("text", "")
    # heuristic: look for LLB decision markers
    low = text.lower()
    if "hard veto" in low or "veto" in low or "blocked" in low or "gate 1" in low and "failure" in low:
        code = -1
    elif "+1 allow" in low or "allowed" in low or "pass" in low:
        code = 1
    elif "0 warn" in low or "hold" in low or "soft_block" in low:
        code = 0
    else:
        code = 1 if res.get("isError") is False else -1
    return code, text

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "validate":
        path, op = sys.argv[2], sys.argv[3]
        args = {"path": path, "operation": op}
        if len(sys.argv) > 4: args["intent_goal"] = sys.argv[4]
        if len(sys.argv) > 5: args["intent_justification"] = sys.argv[5]
        msg = _rpc("llb_validate", args)
    elif cmd == "check":
        args = {"path": sys.argv[2]}
        if len(sys.argv) > 3: args["command"] = sys.argv[3]
        msg = _rpc("llb_check", args)
    elif cmd == "classify":
        args = {"path": sys.argv[2], "operation": sys.argv[3]}
        msg = _rpc("llb_classify", args)
    elif cmd == "write":
        path = sys.argv[2]
        with open(sys.argv[3]) as f: content = f.read()
        op = sys.argv[4] if len(sys.argv) > 4 else "OVERWRITE"
        args = {"path": path, "content": content, "operation": op}
        if len(sys.argv) > 5: args["intent_goal"] = sys.argv[5]
        if len(sys.argv) > 6: args["intent_justification"] = sys.argv[6]
        msg = _rpc("llb_write_safe", args)
    else:
        print("unknown command:", cmd); sys.exit(2)
    code, text = _decision(msg)
    print(text)
    sys.exit(0 if code == 1 else 1)

if __name__ == "__main__":
    main()
