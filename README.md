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


## Week 6 — VXLAN data centre

The data centre has cedar, maple and willow on `10.95.0.0/24`. Research (VNI 9510) spans all three hypervisors with four VMs; studio (VNI 9520) has three VMs across cedar and willow. Both use overlapping `10.95.50.0/24` addresses, isolated by separate tenant bridges and VNIs. `build_overlay.py` derives bridge, VM-port, VXLAN and head-end replication commands from YAML. `check_mtu()` refuses an incompatible design before constructing any network.

The final `overlay.yaml` selects tenant MTU 1500 and underlay MTU 9000. `blackhole.yaml` is an exact copy of the initial all-1500 design. The requested 1950/1500 “Fix A” is mathematically invalid and retained as a rejected case in `mtu_a.yaml`; the working reduced-MTU alternative is `mtu_a_reduced.yaml` (1450/1500). `mtu_b.yaml` is the selected jumbo solution. Neither a 1950-byte overlay nor a permissive receive path solves the underlay size budget.

### Validation and evidence status

All seven automated validation tests pass. Live experiments completed in disposable Docker containers on 20 November 2026. All 18 ordered same-tenant VM pairs passed; the overlapping-address isolation capture contained zero ARP/ICMP packets at the other tenant, and willow captured the initial VNI 9510 ARP flood. Raw output is in `evidence6/connectivity.txt`, `isolation.txt` and `flood.txt`.

The corrected 1450/1500 fix passed payload 1422 and rejected 1423, receiving 1.346 Gbit/s. The selected 1500/9000 fix passed 1472 and rejected 1473, receiving 1.413 Gbit/s. The forced all-1500 design had a measured 1422/1423 boundary but TCP still received 1.342 Gbit/s after path-MTU adaptation. A persistent TCP failure is therefore not claimed for that configuration.

Parts 1–6 are recorded in `evidence6/lab.txt`: namespace/veth inspection, manual red/blue bridge ping, IPv4 VXLAN capture, IPv6 underlay connectivity and MTU checks. Underlay/overlay receiver rates were 2.642/1.795 Gbit/s. Reducing only the receiving underlay to 1400 produced a 1326/1327 boundary, 29 additional receive drops and a JSON receiver rate of zero; restoring 1500 restored ping. The four-byte receive tolerance is specific to this tested virtual path. The initial oversized 1423-byte lab probe had partial success before a local PMTU error. Single-run software throughput values are not a controlled performance ranking.

Part 7 inspected Alpine Linux 3.21, its interface and processes, then removed the temporary container (`evidence6/docker.txt`). BusyBox lacks `ip -br`; `ip link show` completed the inspection. Initial Docker startup failures and the kernel MTU setup rejection are retained as historical diagnostics. Setup now uses temporary underlay headroom before restoring the requested MTU. Previous coursework is unchanged.

See [the reproduction guide](WEEK6-LAB.md) for exact commands for all seven experiments and D5, address/MAC assignments, expected calculations, prerequisites and safe cleanup. The exact five wrap-up prompts and Week 5 P4 sources are absent from this checkout and its available history. The following five answers cover the relevant topics; they cannot be certified as matching an unavailable handout.

### Five lab wrap-up topics

1. **How do Mininet hosts use processes and namespaces?** A Mininet host is normally a shell process in its own network namespace. Its interfaces, routes and neighbour table are isolated, but it shares the Linux kernel and usually the filesystem with other hosts. A veth pair acts as a cable between the host namespace and the switch namespace. Match `dump` PIDs to `lsns`, and correlate interface peer indexes with `ip -o link`; the actual shell PIDs, namespaces and peer indexes are recorded in evidence6/lab.txt.

2. **What does VXLAN encapsulate, and how does it compare with Week 5?** VXLAN transports a guest Ethernet frame within UDP/IP. The underlay forwards between VTEP addresses; the overlay carries guest MAC/IP identities. IPv4 VXLAN costs 50 bytes beyond the inner IP packet; IPv6 costs 70. Only the VTEPs need to decode VXLAN. Week 5 code and `vtep.p4` are not present, so its header size, participating devices and loop-prevention implementation cannot be asserted. A custom P4 tunnel requires its endpoint programs to recognise its custom headers; further transit requirements depend on the missing implementation. This topology uses one VXLAN bridge port per tenant and no local bridge cycle. Bridges do not normally forward a received frame back through its ingress VXLAN port; underlay routing and consistent attachment still need to prevent loops. The Week 5 comparison remains incomplete pending its source.

3. **How do flood-and-learn and overlapping addresses coexist?** Each tenant has its own bridge and VNI. All-zero VXLAN FDB entries replicate broadcasts and unknown unicast only to participating remote hypervisors. Received source MACs can populate bridge and VTEP learning tables; subsequent known unicast uses the appropriate remote mapping. Res2 and art2 share `10.95.50.11`, but their MACs and VNIs differ. The isolation test must observe research ping success while studio art2 receives no corresponding ARP/ICMP. Both observations passed in evidence6/isolation.txt. A broadcast in a 50-VTEP VNI needs 49 ingress-replicated copies; EVPN distributes remote MAC/IP reachability and can reduce address-resolution flooding.

4. **Why can small packets work while large packets fail?** An inner MTU of 1500 needs a 1550-byte IPv4 VXLAN underlay. Small pings fit, but larger packets can be dropped at a tunnel or receiving interface; TCP can establish a connection and then stall on full segments. A 1500 underlay gives a safe inner MTU of 1450 and an IPv4 ICMP payload budget of 1422. With a receiving underlay reduced to 1400, the strict predicted payload budget is 1322. A possible four-byte Linux receive tolerance must be measured rather than assumed. Inner DF does not alone guarantee outer DF; inspect captures, fragmentation settings and before/after counters. The measured receiving-side boundary was 1326/1327, with receiver drops rising by 29 and zero received iperf3 throughput; restoring MTU restored ping.

5. **Which MTU plan and virtualisation model suit this lab?** For a managed data centre I select jumbo underlay 9000 with tenant MTU 1500, preserving standard guest settings while providing tunnel headroom. All fabric paths must support it; 1450/1500 is a valid fallback when fabric MTUs cannot change. The measured rates above are single runs, not a controlled performance ranking. Docker additionally supplies an image/filesystem, process isolation and configurable resource controls, whereas Mininet chiefly supplies lightweight network namespaces for processes. Both share a Linux kernel. The temporary Alpine inspection must run on the laptop host; its attempted execution is recorded in `evidence6/docker.txt`, including successful OS/process inspection and the supported interface-command retry.

### Reproduce the assignment

Run privileged networking only inside the intended course container, from this repository root:

```bash
python3 -m unittest discover -s tests -v
python3 build_overlay.py overlay.yaml
# Exit the CLI before starting another network.
python3 run_week6_experiments.py flood
python3 run_week6_experiments.py isolation
python3 run_week6_experiments.py blackhole
python3 run_week6_experiments.py fixes
python3 run_week6_experiments.py connectivity
python3 make_page6.py overlay.yaml
```

The collector builds a fresh network for each experiment and stops it afterward. It refuses unexpected live failures and records receiver throughput only from successful iperf3 JSON. It has now run successfully in the privileged course image. Do not use `pingall` with overlapping tenant addresses. The full-mesh collector passed every ordered same-tenant pair. Run python3 run_week6_lab.py separately for Parts 1–6.

`page6.yaml` answers every supplied assignment question, with missing measurements clearly identified. The generated local page is `docs/week6/index.html`. The intended submission URL is https://haiqalshii.github.io/wic2005-programmable-networks/week6/ ; publication status must be checked separately from local generation.

Networking references: [VXLAN encapsulation, RFC 7348](https://www.rfc-editor.org/rfc/rfc7348.html), [Linux VXLAN forwarding](https://www.kernel.org/doc/html/latest/networking/vxlan.html), and [EVPN control-plane learning, RFC 8365](https://www.rfc-editor.org/rfc/rfc8365.html).

### Week 6 AI-use declaration — Level 3 Open AI

OpenAI Codex was used to assist with code implementation, debugging, validation, experiment execution where possible, and documentation. It implemented the VXLAN/MTU functions, generated reproducible experiment procedures, ran static checks, recorded blocked live attempts and prepared the webpage answers. No successful networking measurement was fabricated. This work is not claimed to have been completed independently without AI assistance; live results were collected by Codex; the Week 5 comparison still requires the unavailable source.
