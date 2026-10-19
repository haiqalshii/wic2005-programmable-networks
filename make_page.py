#!/usr/bin/env python3
"""Week 2 assignment: generate your network's web page from the same data that builds it.

Run it inside the lab container, from your netlab folder:
    python3 make_page.py topology.yaml

It reads your topology file, checks it with the same checks build_topo.py uses (so a broken
network never gets published), and writes docs/index.html. The page includes:
  - your network, from topology.yaml
  - your evidence, from the files in evidence/
  - your answers, from page.yaml
GitHub Pages then publishes the docs folder (Settings -> Pages -> main, /docs).

Two parts are yours to write: links_section() and mermaid_diagram(). Look for TODO.
"""
import datetime
import html
import json
import os
import sys

import yaml

# The same functions build_topo.py uses: one data model, one set of checks, two outputs.
from build_topo import check, check_mine, load

# (id, file, title) for each piece of evidence. Save each file from your running network.
EVIDENCE = [
    ("pingall", "evidence/pingall.txt", "pingall: every host reaches every other"),
    ("neigh", "evidence/neigh.txt", "h1's neighbour table: ARP and Neighbour Discovery"),
    ("macs", "evidence/macs.txt", "What a switch's data plane learned: brctl showmacs"),
    ("dad", "evidence/dad.txt", "A duplicate address: IPv6 notices, IPv4 doesn't"),
    ("check", "evidence/check.txt", "check() stopping bad data before it's built"),
]


def esc(text):
    return html.escape(str(text))


def hosts_section(spec):
    """A table of hosts: name, addresses, and the switch each one is plugged into. (Worked example.)"""
    plugged_into = {}
    for a, b in spec["links"]:
        if a in spec["switches"]:
            plugged_into[b] = a
        elif b in spec["switches"]:
            plugged_into[a] = b
    rows = "".join(
        f"<tr><td>{esc(h['name'])}</td><td><code>{esc(h['ip'])}</code></td>"
        f"<td><code>{esc(h.get('ipv6', ''))}</code></td><td>{esc(plugged_into.get(h['name'], '—'))}</td></tr>"
        for h in spec["hosts"]
    )
    return (
        "<table><thead><tr><th>Host</th><th>IPv4</th><th>IPv6</th><th>Switch</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def links_section(spec):
    """TODO (assignment): return HTML listing every link in spec["links"].

    For example, for links [h1, s1] and [s1, s2] return:
        <ul><li>h1 — s1</li><li>s1 — s2</li></ul>
    Use esc() on every name, as hosts_section() does.
    """
    items = "".join(f"<li>{esc(a)} — {esc(b)}</li>" for a, b in spec["links"])
    return f"<ul>{items}</ul>"


def mermaid_diagram(spec):
    """TODO (assignment): return Mermaid text that draws the network, built from spec["links"].

    Mermaid turns text like this into a diagram in the browser:
        graph LR
          h1 --- s1
          s1 --- s2
    Start with "graph LR", then add one line per link. For extra credit, show each host's
    IPv4 address in its box, e.g.  h1["h1<br>10.NN.0.1"] --- s1
    """
    host_ip = {h["name"]: h["ip"].split("/")[0] for h in spec["hosts"]}

    def node(name):
        if name in host_ip:
            return f'{name}["{name}<br>{host_ip[name]}"]'
        return f'{name}(["{name}"])'

    # Drawn top-down: Mermaid places the first node of each line above the second, so put
    # switch-to-switch links first and always write host links switch-first. Hosts then hang
    # below the switch they're plugged into.
    switch_links = [(a, b) for a, b in spec["links"] if a not in host_ip and b not in host_ip]
    host_links = [(b, a) if a in host_ip else (a, b) for a, b in spec["links"] if (a, b) not in switch_links]

    lines = ["graph TD"] + [f"  {node(a)} --- {node(b)}" for a, b in switch_links + host_links]
    lines.append(f"  class {','.join(spec['switches'])} switch")
    lines.append(f"  class {','.join(host_ip)} host")
    return "\n".join(lines)


def evidence_section(ev_id, path, title):
    if os.path.exists(path) and open(path).read().strip():
        body = f'<pre id="evidence-{ev_id}">{esc(open(path).read().rstrip())}</pre>'
    else:
        print(f"WARNING: {path} is missing or empty")
        body = f'<pre id="evidence-{ev_id}" class="missing">Missing: {esc(path)}</pre>'
    return f'<div class="card"><h3>{esc(title)}</h3>\n<p class="file">{esc(path)}</p>\n{body}</div>'


def answers_section(page):
    parts = []
    for key, qa in page.get("answers", {}).items():
        answer = str(qa.get("answer") or "").strip()
        if not answer:
            print(f"WARNING: page.yaml has no answer for '{key}'")
            answer = "(Not answered yet.)"
        paragraphs = "".join(f"<p>{esc(p.strip())}</p>" for p in answer.split("\n\n") if p.strip())
        parts.append(f'<section id="answer-{esc(key)}"><h3>{esc(qa.get("question", key))}</h3>{paragraphs}</section>')
    return "\n".join(parts)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Network {last4}: built from data</title>
<style>
  :root {{
    --bg: #f5f5f7; --card: #ffffff; --text: #1d1d1f; --muted: #6e6e73; --line: #d2d2d7;
    --accent: #0071e3; --code-bg: #f5f5f7; --term-bg: #1d1d1f; --term-text: #f5f5f7;
    --switch: #0071e3; --host: #ffffff; --nav: rgba(251, 251, 253, .8);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #000000; --card: #1c1c1e; --text: #f5f5f7; --muted: #a1a1a6; --line: #38383a;
      --accent: #2997ff; --code-bg: #2c2c2e; --term-bg: #0b0b0c; --term-text: #f5f5f7;
      --switch: #2997ff; --host: #2c2c2e; --nav: rgba(22, 22, 23, .8);
    }}
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); line-height: 1.5;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased; }}
  nav {{ position: sticky; top: 0; z-index: 10; background: var(--nav); backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid var(--line); }}
  nav .inner {{ max-width: 980px; margin: 0 auto; padding: 0 16px; height: 48px; display: flex; align-items: center;
    gap: 22px; font-size: .78rem; overflow-x: auto; white-space: nowrap; }}
  nav .brand {{ font-weight: 600; font-size: .92rem; margin-right: auto; }}
  nav a {{ color: var(--text); opacity: .8; text-decoration: none; }} nav a:hover {{ opacity: 1; }}
  main {{ max-width: 980px; margin: 0 auto; padding: 0 16px 80px; }}
  header {{ text-align: center; padding: 72px 0 40px; }}
  .eyebrow {{ color: var(--accent); font-weight: 600; font-size: 1rem; margin: 0 0 8px; }}
  h1 {{ font-size: clamp(2.4rem, 7vw, 4rem); line-height: 1.05; letter-spacing: -.02em; font-weight: 700; margin: 0 0 16px; }}
  #summary {{ font-size: clamp(1.05rem, 2.4vw, 1.3rem); color: var(--muted); max-width: 40rem; margin: 0 auto 8px; }}
  .meta {{ color: var(--muted); font-size: .8rem; margin: 16px 0 0; }}
  .repo {{ display: inline-block; margin-top: 24px; background: var(--accent); color: #fff; text-decoration: none;
    padding: 10px 22px; border-radius: 980px; font-size: .95rem; }}
  .repo:hover {{ filter: brightness(1.1); }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 8px 0 0; }}
  .stat {{ background: var(--card); border-radius: 18px; padding: 24px; text-align: center; }}
  .stat b {{ display: block; font-size: 2.6rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.1; }}
  .stat span {{ color: var(--muted); font-size: .9rem; }}
  h2 {{ font-size: clamp(1.8rem, 4.5vw, 2.6rem); letter-spacing: -.015em; font-weight: 700; margin: 80px 0 24px; }}
  h3 {{ font-size: 1.15rem; font-weight: 600; margin: 0 0 6px; }}
  .card {{ background: var(--card); border-radius: 18px; padding: 28px; margin-bottom: 16px; overflow: hidden; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .92rem; }}
  th {{ color: var(--muted); font-weight: 500; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
  th, td {{ border-bottom: 1px solid var(--line); padding: 12px 8px; text-align: left; }}
  tr:last-child td {{ border-bottom: 0; }}
  .table-wrap {{ overflow-x: auto; }}
  code {{ font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: .86em; background: var(--code-bg);
    padding: 2px 6px; border-radius: 6px; }}
  #links ul {{ list-style: none; padding: 0; margin: 12px 0 0; display: flex; flex-wrap: wrap; gap: 8px; }}
  #links li {{ background: var(--code-bg); border-radius: 980px; padding: 6px 14px; font-size: .9rem; }}
  pre {{ background: var(--term-bg); color: var(--term-text); padding: 18px; border-radius: 12px; overflow-x: auto;
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: .8rem; line-height: 1.55; margin: 12px 0 0; }}
  pre.mermaid {{ background: none; color: inherit; text-align: center; padding: 8px 0 0; }}
  pre.missing {{ background: #fff1f0; color: #b42318; }}
  #diagram .node.switch rect, #diagram .node.switch path {{ fill: var(--switch) !important; stroke: var(--switch) !important; }}
  #diagram .node.switch .nodeLabel {{ color: #fff !important; font-weight: 600; }}
  #diagram .node.host rect {{ fill: var(--host) !important; stroke: var(--line) !important; rx: 10px; ry: 10px; }}
  #diagram .node.host .nodeLabel {{ color: var(--text) !important; }}
  #diagram .edgePath path, #diagram .flowchart-link {{ stroke: var(--muted) !important; stroke-width: 1.5px !important; }}
  .file {{ color: var(--muted); font-size: .8rem; margin: 0; font-family: "SF Mono", ui-monospace, Menlo, monospace; }}
  #evidence .card:first-child {{ grid-column: 1 / -1; }}
  #answers section {{ background: var(--card); border-radius: 18px; padding: 28px; margin-bottom: 16px; }}
  #answers h3 {{ font-size: 1.2rem; margin-bottom: 10px; }}
  #answers p {{ color: var(--muted); margin: 0 0 10px; }} #answers p:last-child {{ margin: 0; }}
  footer {{ text-align: center; color: var(--muted); font-size: .78rem; padding: 0 16px 48px; }}
  @media (max-width: 720px) {{
    .grid {{ grid-template-columns: 1fr; }} .stat {{ padding: 18px 8px; }} .stat b {{ font-size: 2rem; }}
    .card, #answers section {{ padding: 20px; }} header {{ padding-top: 48px; }}
  }}
</style>
</head>
<body>
<nav><div class="inner">
  <span class="brand">Network {last4}</span>
  <a href="#network">Network</a><a href="#diagram-card">Diagram</a><a href="#evidence-heading">Evidence</a><a href="#answers-heading">Learned</a>
</div></nav>
<main>
<header>
  <p class="eyebrow">WIC2005 · Programmable Networks</p>
  <h1>My network,<br>built from data.</h1>
  <p id="summary">{n_switches} switches, {n_hosts} hosts and {n_links} links, on IPv4 <code>{v4_block}</code> and IPv6 <code>{v6_block}</code>.
  The same file builds this network in Mininet and generates this page.</p>
  <a class="repo" id="repository" href="{repo}">View the repository ›</a>
  <p class="meta">Student ID ending {last4} · generated from <code>{source}</code> by <code>make_page.py</code> on {today}</p>
</header>

<div class="stats">
  <div class="stat"><b>{n_switches}</b><span>Switches</span></div>
  <div class="stat"><b>{n_hosts}</b><span>Hosts</span></div>
  <div class="stat"><b>{n_links}</b><span>Links</span></div>
</div>

<h2 id="network">The network.</h2>
<div class="card" id="diagram-card">
  <h3>Diagram</h3>
  <pre class="mermaid" id="diagram">{diagram}</pre>
</div>
<div class="card">
  <h3>Hosts</h3>
  <section id="hosts" class="table-wrap">{hosts}</section>
</div>
<div class="card">
  <h3>Links</h3>
  <section id="links">{links}</section>
</div>

<h2 id="evidence-heading">Evidence from the running network.</h2>
<section id="evidence" class="grid">{evidence}</section>

<h2 id="answers-heading">What I learned.</h2>
<section id="answers">{answers}</section>
</main>
<footer>Generated by make_page.py from {source}. One data model, two outputs: a running network and its documentation.</footer>

<script type="application/json" id="topology-data">{data}</script>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({{
    startOnLoad: true,
    theme: "base",
    flowchart: {{ curve: "basis", nodeSpacing: 36, rankSpacing: 64, htmlLabels: true }},
    themeVariables: {{
      fontFamily: '-apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif',
      fontSize: "14px",
      lineColor: dark ? "#a1a1a6" : "#6e6e73",
    }},
  }});
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 make_page.py <topology.yaml|topology.json>")
    source = sys.argv[1]
    spec = load(source)

    problems = check_mine(spec) + check(spec)
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        sys.exit("Fix the description first: a broken network doesn't get published.")

    with open("page.yaml") as f:
        page = yaml.safe_load(f)
    last4 = str(spec["student_id_last4"])

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w") as f:
        f.write(
            PAGE.format(
                last4=esc(last4),
                source=esc(source),
                today=datetime.date.today().isoformat(),
                n_switches=len(spec["switches"]),
                n_hosts=len(spec["hosts"]),
                n_links=len(spec["links"]),
                v4_block=f"10.{int(last4[2:])}.0.0/16",
                v6_block=f"fd00:{last4}::/32",
                repo=esc(page.get("repository", "")),
                hosts=hosts_section(spec),
                links=links_section(spec),
                diagram=esc(mermaid_diagram(spec)),
                evidence="\n".join(evidence_section(*e) for e in EVIDENCE),
                answers=answers_section(page),
                # The page carries its own data model; "</" is escaped so it can't end the script tag.
                data=json.dumps(spec, indent=2).replace("</", "<\\/"),
            )
        )
    print("Wrote docs/index.html")


if __name__ == "__main__":
    main()
