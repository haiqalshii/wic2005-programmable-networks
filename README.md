# WIC2005 Programmable Networks Lab Portfolio

This repository contains my WIC2005 lab work on describing, validating, building, and testing networks as data.

## Week 2

The Week 2 work describes a switched topology in YAML, validates it before building, and generates the main GitHub Pages site in `docs/index.html`.

Key files:

- `topology.yaml` — the switched-network description
- `build_topo.py` — validates and builds the topology
- `make_page.py` and `page.yaml` — generate the Week 2 page
- `evidence/` — validation, addressing, neighbour, and connectivity evidence

## Week 3

The Week 3 assignment builds a routed network using four Linux routers and four LANs. The routers form a square, which provides a redundant physical path. The network uses static routes, including the summary route `10.95.40.0/23` for the LANs `10.95.40.0/24` and `10.95.41.0/24`.

Key files:

- `network.yaml` — routers, LANs, links, and static routes
- `build_routed.py` — validates every host-to-host path before building the network
- `loop.yaml` and `missing.yaml` — deliberately broken configurations used to test the validator
- `make_page3.py` and `page3.yaml` — generate `docs/week3/index.html`
- `evidence3/` — routing tables, traceroutes, summary-route proof, link-failure output, and validation results

### Run the routed network

Run these commands inside the privileged Mininet container from the repository directory:

```bash
mn -c
python3 build_routed.py network.yaml
```

The program checks the network description first. It only opens the Mininet CLI when every host-to-host path is valid.

### Generate the Week 3 page

```bash
python3 make_page3.py network.yaml
```

The generated page is written to `docs/week3/index.html` and is published through GitHub Pages.

## AI use

I used OpenAI Codex to troubleshoot my Docker and Mininet environment, explain lab commands and networking results, help plan the four-router topology and address scheme, suggest implementations for the path validator and routing-table generator, and review the collected evidence. I ran and tested the commands and code in my own environment, reviewed the resulting routes and packet paths, and made sure I could explain the work included in this repository.
