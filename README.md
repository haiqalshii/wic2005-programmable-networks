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

The automated validation tests pass for addressing, placement, command generation, peer replication, generalisation and MTU boundaries. Real black-hole validation output is in `evidence6/check.txt`. Live Mininet experiments are blocked because Mininet is not installed in this WSL environment, and Docker engine checks/Alpine attempts failed or timed out. `evidence6/flood.txt`, `isolation.txt`, `blackhole.txt` and `fixes.txt` record genuine blocked attempts. They contain no successful captures, measured payload limits or receiver throughput. VM connectivity, runtime isolation, the seven practical experiments and throughput comparisons remain unverified.

See [the reproduction guide](WEEK6-LAB.md) for exact commands for all seven experiments and D5, address/MAC assignments, expected calculations, prerequisites and safe cleanup. The exact five wrap-up prompts and Week 5 P4 sources are absent from this checkout and its available history. The following five answers cover the relevant topics; they cannot be certified as matching an unavailable handout.

### Five lab wrap-up topics

1. **How do Mininet hosts use processes and namespaces?** A Mininet host is normally a shell process in its own network namespace. Its interfaces, routes and neighbour table are isolated, but it shares the Linux kernel and usually the filesystem with other hosts. A veth pair acts as a cable between the host namespace and the switch namespace. Match `dump` PIDs to `lsns`, and correlate interface peer indexes with `ip -o link`; the blocked environment prevented observing the actual lab pairs here.

2. **What does VXLAN encapsulate, and how does it compare with Week 5?** VXLAN transports a guest Ethernet frame within UDP/IP. The underlay forwards between VTEP addresses; the overlay carries guest MAC/IP identities. IPv4 VXLAN costs 50 bytes beyond the inner IP packet; IPv6 costs 70. Only the VTEPs need to decode VXLAN. Week 5 code and `vtep.p4` are not present, so its header size, participating devices and loop-prevention implementation cannot be asserted. A custom P4 tunnel requires its endpoint programs to recognise its custom headers; further transit requirements depend on the missing implementation. This topology uses one VXLAN bridge port per tenant and no local bridge cycle. Bridges do not normally forward a received frame back through its ingress VXLAN port; underlay routing and consistent attachment still need to prevent loops. The Week 5 comparison remains incomplete pending its source.

3. **How do flood-and-learn and overlapping addresses coexist?** Each tenant has its own bridge and VNI. All-zero VXLAN FDB entries replicate broadcasts and unknown unicast only to participating remote hypervisors. Received source MACs can populate bridge and VTEP learning tables; subsequent known unicast uses the appropriate remote mapping. Res2 and art2 share `10.95.50.11`, but their MACs and VNIs differ. The isolation test must observe research ping success while studio art2 receives no corresponding ARP/ICMP. Those observations are pending. A broadcast in a 50-VTEP VNI needs 49 ingress-replicated copies; EVPN distributes remote MAC/IP reachability and can reduce address-resolution flooding.

4. **Why can small packets work while large packets fail?** An inner MTU of 1500 needs a 1550-byte IPv4 VXLAN underlay. Small pings fit, but larger packets can be dropped at a tunnel or receiving interface; TCP can establish a connection and then stall on full segments. A 1500 underlay gives a safe inner MTU of 1450 and an IPv4 ICMP payload budget of 1422. With a receiving underlay reduced to 1400, the strict predicted payload budget is 1322. A possible four-byte Linux receive tolerance must be measured rather than assumed. Inner DF does not alone guarantee outer DF; inspect captures, fragmentation settings and before/after counters. The corresponding real packet boundaries and rates remain unmeasured.

5. **Which MTU plan and virtualisation model suit this lab?** For a managed data centre I select jumbo underlay 9000 with tenant MTU 1500, preserving standard guest settings while providing tunnel headroom. All fabric paths must support it; 1450/1500 is a valid fallback when fabric MTUs cannot change. No throughput ranking is claimed without actual receiver measurements. Docker additionally supplies an image/filesystem, process isolation and configurable resource controls, whereas Mininet chiefly supplies lightweight network namespaces for processes. Both share a Linux kernel. The temporary Alpine inspection must run on the laptop host; its attempted execution is recorded in `evidence6/docker.txt`, without a successful container result.

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

The collector builds a fresh network for each experiment and stops it afterward. It refuses unexpected live failures and records receiver throughput only from successful iperf3 JSON. It is syntax-checked but has not been runtime-verified on Mininet here. Do not use `pingall` with overlapping tenant addresses. Check every VM pair within each tenant as described in the guide, then update the measurement-dependent answers and regenerate the page after obtaining real results.

`page6.yaml` answers every supplied assignment question, with missing measurements clearly identified. The generated local page is `docs/week6/index.html`. The intended submission URL is https://haiqalshii.github.io/wic2005-programmable-networks/week6/ ; publication status must be checked separately from local generation.

Networking references: [VXLAN encapsulation, RFC 7348](https://www.rfc-editor.org/rfc/rfc7348.html), [Linux VXLAN forwarding](https://www.kernel.org/doc/html/latest/networking/vxlan.html), and [EVPN control-plane learning, RFC 8365](https://www.rfc-editor.org/rfc/rfc8365.html).

### Week 6 AI-use declaration — Level 3 Open AI

OpenAI Codex was used to assist with code implementation, debugging, validation, experiment execution where possible, and documentation. It implemented the VXLAN/MTU functions, generated reproducible experiment procedures, ran static checks, recorded blocked live attempts and prepared the webpage answers. No successful networking measurement was fabricated. This work is not claimed to have been completed independently without AI assistance; live results and the unavailable Week 5 material still require verification before final submission.
