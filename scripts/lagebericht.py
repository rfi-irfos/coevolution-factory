#!/usr/bin/env python3
"""
lagebericht.py — RFI-IRFOS weekly situation report.

Reads ALL local git repos under PROJECTS_DIR, collects commits of the last
N days, checks production-deploy status (fly.toml + DEPLOY_OK signal), and
writes a bilingual DE+EN markdown report to ~/Desktop.

This is the Sunday-evening snapshot skill. It only READS (T0) — no LLB gate
needed. Run:  python3 scripts/lagebericht.py [days] [org]

Default: days=7, org=rfi-irfos
"""
import os, sys, subprocess, datetime, json

PROJECTS_DIR = "/home/eri-irfos/projects"
DESKTOP = os.path.expanduser("~/Desktop")
TARGET_ORG = sys.argv[2] if len(sys.argv) > 2 else "rfi-irfos"
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
SINCE = (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()
TODAY = datetime.date.today().isoformat()

def run(cmd, cwd=None):
    try:
        return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception as e:
        return f"ERR:{e}"

def discover_repos():
    repos = []
    for name in sorted(os.listdir(PROJECTS_DIR)):
        d = os.path.join(PROJECTS_DIR, name)
        if not os.path.isdir(os.path.join(d, ".git")):
            continue
        remote = run(f"git -C '{d}' remote get-url origin").strip()
        if TARGET_ORG in remote:
            repos.append((name, d, remote))
    return repos

def collect(repos):
    results = []
    for name, d, remote in repos:
        log = run(f"git -C '{d}' log --since='{SINCE}' --pretty=format:'%h|%ad|%an|%s' --date=short")
        commits = [l for l in log.splitlines() if l and not l.startswith("ERR:")]
        fly = bool(run(f"find '{d}' -maxdepth 3 -name fly.toml 2>/dev/null").strip())
        # deploy signal: recent commit msg mentions deploy
        deploy_sig = run(f"git -C '{d}' log --since='{SINCE}' --pretty=format:'%s' --date=short")
        shipped = any(k in deploy_sig.lower() for k in ["deploy_ok", "fly deploy", "deployed", "deploy success"])
        last = commits[0].split("|") if commits else None
        # dedupe by remote (autonomous-ai-co -> coevolution-factory)
        results.append({
            "name": name, "remote": remote, "dir": d,
            "count": len(commits), "commits": commits,
            "fly": fly, "shipped": shipped, "last": last,
        })
    return results

def summarize(results):
    active = [r for r in results if r["count"] > 0]
    total = sum(r["count"] for r in results)
    prod = [r for r in results if r["fly"]]
    unshipped = [r for r in active if r["fly"] and not r["shipped"]]
    return active, total, prod, unshipped

def render_de(results, active, total, prod, unshipped):
    L = []
    L.append(f"# LAGEBERICHT — Woche {SINCE} bis {TODAY}")
    L.append(f"Generiert: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append(f"Aktive Repos: {len(active)} | Gesamt-Commits: {total} | Production-relevant: {len(prod)}")
    L.append("")
    L.append("## Zusammenfassung")
    if active:
        top = sorted(active, key=lambda r: -r["count"])[0]
        L.append(f"Diese Woche dominiert **{top['name']}** mit {top['count']} Commits. "
                 f"{len(active)} Repos hatten Aktivität, {len(prod)} sind production-relevant.")
    else:
        L.append("Keine Aktivität diese Woche in den überwachten Repos.")
    L.append("")
    for r in active:
        L.append(f"### {r['name']}")
        L.append(f"- Commits diese Woche: {r['count']}")
        if r["last"]:
            parts = r["last"]
            h = parts[0] if len(parts)>0 else ""
            dt = parts[1] if len(parts)>1 else ""
            an = parts[2] if len(parts)>2 else ""
            msg = parts[3] if len(parts)>3 else ""
            L.append(f"- Letzter Commit: {h} ({dt}, {an}) — {msg}")
        L.append("- Highlights:")
        for c in r["commits"][:3]:
            parts = c.split("|")
            L.append(f"  - {parts[3] if len(parts)>3 else c}")
        dep = "bestätigt" if r["shipped"] else ("UNBEKANNT — verifizieren" if r["fly"] else "n/a (kein fly.toml)")
        L.append(f"- Production: fly.toml {'ja' if r['fly'] else 'nein'} | Deploy: {dep}")
        L.append("")
    if unshipped:
        L.append("## Offene Punkte (Code geändert, Deploy unbestätigt)")
        for r in unshipped:
            L.append(f"- **{r['name']}**: {r['count']} Commits, aber kein Deploy-Signal gefunden.")
        L.append("")
    return "\n".join(L)

def render_en(results, active, total, prod, unshipped):
    L = []
    L.append(f"# WEEKLY REPORT — {SINCE} to {TODAY}")
    L.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append(f"Active repos: {len(active)} | Total commits: {total} | Production-relevant: {len(prod)}")
    L.append("")
    L.append("## Summary")
    if active:
        top = sorted(active, key=lambda r: -r["count"])[0]
        L.append(f"This week **{top['name']}** dominated with {top['count']} commits. "
                 f"{len(active)} repos had activity, {len(prod)} are production-relevant.")
    else:
        L.append("No activity this week in the monitored repos.")
    L.append("")
    for r in active:
        L.append(f"### {r['name']}")
        L.append(f"- Commits this week: {r['count']}")
        if r["last"]:
            parts = r["last"]
            L.append(f"- Last commit: {parts[0] if len(parts)>0 else ''} ({parts[1] if len(parts)>1 else ''}, {parts[2] if len(parts)>2 else ''}) — {parts[3] if len(parts)>3 else ''}")
        L.append("- Highlights:")
        for c in r["commits"][:3]:
            parts = c.split("|")
            L.append(f"  - {parts[3] if len(parts)>3 else c}")
        dep = "confirmed" if r["shipped"] else ("UNKNOWN — verify" if r["fly"] else "n/a (no fly.toml)")
        L.append(f"- Production: fly.toml {'yes' if r['fly'] else 'no'} | Deploy: {dep}")
        L.append("")
    if unshipped:
        L.append("## Open items (code changed, deploy unconfirmed)")
        for r in unshipped:
            L.append(f"- **{r['name']}**: {r['count']} commits but no deploy signal found.")
        L.append("")
    return "\n".join(L)

def main():
    repos = discover_repos()
    # dedupe by remote URL
    seen = {}
    for name, d, remote in repos:
        seen[remote] = (name, d, remote)
    repos = list(seen.values())
    results = collect(repos)
    active, total, prod, unshipped = summarize(results)
    de = render_de(results, active, total, prod, unshipped)
    en = render_en(results, active, total, prod, unshipped)
    os.makedirs(DESKTOP, exist_ok=True)
    de_path = os.path.join(DESKTOP, f"LAGEBERICHT_{TODAY}.md")
    en_path = os.path.join(DESKTOP, f"WEEKLY_REPORT_{TODAY}.md")
    with open(de_path, "w") as f: f.write(de)
    with open(en_path, "w") as f: f.write(en)
    print(f"DE: {de_path}")
    print(f"EN: {en_path}")
    print(f"Active repos: {len(active)} | Total commits: {total} | Production: {len(prod)} | Unshipped flags: {len(unshipped)}")

if __name__ == "__main__":
    main()
