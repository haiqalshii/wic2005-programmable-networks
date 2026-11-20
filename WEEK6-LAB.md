# Week 6 reproduction guide and measurement status

Run from this repository root (the course's `netlab` working directory). The downloaded starters already lived here; none was downloaded again. Use an isolated, privileged course Mininet container for Parts 1–6 and D5. Do not run these commands in a shared host network namespace. Stop each Mininet session with `exit` before starting another. There is no need for system-wide `mn -c` cleanup.

## Recorded status

This execution environment is an unprivileged WSL shell without the Mininet Python package. Its sandbox also denies network-interface inspection. Docker Desktop returned an engine error and the native Docker connection timed out. See `evidence6/environment.txt`, `evidence6/docker.txt`, and the experiment logs. Parts 1–7 and D5 packet delivery, captures, MTU boundaries, and receiver throughput are **unmeasured**. The dependency errors are real output, not substitutes for a successful experiment. No bandwidth values are asserted.

The available instructions are the four starters and the task. There is no separate Week 6 handout, exact five lab wrap-up prompts, Week 5 implementation, or `vtep.p4` in the checkout or available Git history. README answers cover five relevant wrap-up topics, explicitly subject to this limitation.

## Part 1 — Mininet processes, namespaces, and veth pairs

Inside the course container:

```bash
mn --topo single,2 --switch lxbr --controller none --ipbase 10.95.0.0/24
```

At the Mininet prompt:

```text
nodes
net
dump
sh lsns -t net -o NS,TYPE,NPROCS,PID,COMMAND
h1 ip -br link
h2 ip -br link
sh ip -br link
h1 ip -o link show h1-eth0
h2 ip -o link show h2-eth0
sh ip -o link show
h1 ping -c 3 10.95.0.2
exit
```

Correlate each host shell PID from `dump` with its namespace in `lsns`. A host is a shell process in a separate network namespace, using the same Linux kernel and filesystem. Processes launched by that shell inherit its network namespace. `net` identifies the host/switch cables; compare veth `ifindex` and `iflink`/`@if...` across namespaces to identify the peer of `h1-eth0` and `h2-eth0`. Do not confuse a namespace inode number with a process ID.

## Part 2 — Build red and blue manually

Use a fresh disposable course container, as root. Confirm the names below are unused before creating them; stop on an error instead of overwriting existing objects.

```bash
ip netns add red
ip netns add blue
ip link add red0 type veth peer name redbr
ip link add blue0 type veth peer name bluebr
ip link set red0 netns red
ip link set blue0 netns blue
ip link add br0 type bridge
ip link set redbr master br0
ip link set bluebr master br0
ip link set br0 up
ip link set redbr up
ip link set bluebr up
ip -n red link set lo up
ip -n blue link set lo up
ip -n red addr add 10.95.9.1/24 dev red0
ip -n blue addr add 10.95.9.2/24 dev blue0
ip -n red link set red0 up
ip -n blue link set blue0 up
ip netns exec red ping -c 3 10.95.9.2
bridge fdb show br br0
```

The bridge learns source MAC addresses on ingress ports. Initial ARP resolves the destination IPv4 address; later unicast frames use learned entries. After recording output, remove only the objects just created:

```bash
ip netns del red
ip netns del blue
ip link del br0
```

Deleting the two namespaces removes their veth pairs when no process holds them open.

## Parts 3 and 4 — IPv4 VXLAN, DF probes, throughput

Start the same fresh two-host Mininet topology as Part 1. At its prompt:

```text
h1 ip link add vx100 type vxlan id 100 local 10.95.0.1 remote 10.95.0.2 dstport 4789 dev h1-eth0
h2 ip link add vx100 type vxlan id 100 local 10.95.0.2 remote 10.95.0.1 dstport 4789 dev h2-eth0
h1 ip addr add 10.95.100.1/24 dev vx100
h2 ip addr add 10.95.100.2/24 dev vx100
h1 ip link set vx100 mtu 1950 up
h2 ip link set vx100 mtu 1950 up
h1 ip -d link show vx100
h1 ip link show h1-eth0
h2 timeout 8s tcpdump -U -nn -e -vv -i h2-eth0 udp port 4789 > /tmp/week6-v4-capture.txt 2>&1 &
sh sleep 1
h1 ping -c 3 10.95.100.2
h1 ping -M do -c 3 -s 1422 10.95.100.2
h1 ping -M do -c 3 -s 1423 10.95.100.2
sh sleep 8
h2 cat /tmp/week6-v4-capture.txt
h2 iperf3 -s -1 -J > /tmp/week6-underlay-server.json 2>&1 &
sh sleep 1
h1 timeout 20s iperf3 -c 10.95.0.2 -t 5 -J
h2 cat /tmp/week6-underlay-server.json
h2 iperf3 -s -1 -J > /tmp/week6-overlay-server.json 2>&1 &
sh sleep 1
h1 timeout 20s iperf3 -c 10.95.100.2 -t 5 -J
h2 cat /tmp/week6-overlay-server.json
```

Record actual `end.sum_received.bits_per_second` from each successful client JSON and corroborate it with server output. Record timeouts and retransmissions rather than reporting zero as a measured rate. The underlay addresses transport the outer UDP/IP packet; overlay addresses identify the tenant endpoints within the encapsulated Ethernet frame.

For IPv4 VXLAN, `14 inner Ethernet + 8 VXLAN + 8 UDP + 20 outer IPv4 = 50` bytes beyond the inner IP packet. Outer Ethernet is outside the underlay IP MTU budget. With a 1500 underlay, the safe tenant MTU is 1450 and the unfragmented ICMP payload is `1450 - 20 - 8 = 1422`. The next payload needs 1501 outer IP bytes. A tunnel MTU of 1950 permits excessively large inner packets; it does not increase the underlay's capacity. Inner `ping -M do` does not alone prove the outer DF policy: inspect `ip -d link` and captures for fragmentation. Kernel behaviour can differ from the simple size budget. Disable segmentation offloads if supported before interpreting TCP results; the assignment builder already does so for VMs.

## Part 5 — IPv6 underlay

Continue the two-host session, keeping the IPv4 tunnel as a separate device:

```text
h1 ip -6 addr add fd00:1995::1/64 dev h1-eth0
h2 ip -6 addr add fd00:1995::2/64 dev h2-eth0
h1 ping -6 -c 3 fd00:1995::2
h1 ip link add vx106 type vxlan id 106 local fd00:1995::1 remote fd00:1995::2 dstport 4789 dev h1-eth0
h2 ip link add vx106 type vxlan id 106 local fd00:1995::2 remote fd00:1995::1 dstport 4789 dev h2-eth0
h1 ip addr add 10.95.106.1/24 dev vx106
h2 ip addr add 10.95.106.2/24 dev vx106
h1 ip -d link show vx106
h2 ip -d link show vx106
h1 ip link set vx106 mtu 1430 up
h2 ip link set vx106 mtu 1430 up
h1 ping -c 3 10.95.106.2
h1 ping -M do -c 3 -s 1402 10.95.106.2
h1 ping -M do -c 3 -s 1403 10.95.106.2
```

Record the kernel's initial MTU before setting it. IPv6's 40-byte base header gives `14 + 8 + 8 + 40 = 70` bytes of overhead, and an inner IPv4 MTU budget of 1430. The supplied `fd00:1995::/32` is used only in this separate IPv6 lab; the data-centre starter is IPv4-only.

## Part 6 — Receive-side MTU mismatch

Continue with IPv4 `vx100` at MTU 1950. Lower only the receiving underlay, so the sender is unaware of the bottleneck:

```text
h2 ip link set h2-eth0 mtu 1400
h2 ip -s link show h2-eth0
h1 ping -M do -c 3 -s 56 10.95.100.2
h1 ping -M do -c 3 -s 1422 10.95.100.2
h1 python3 -c 'import subprocess; r={n:subprocess.run(["ping","-n","-M","do","-c","2","-W","1","-s",str(n),"10.95.100.2"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0 for n in range(1200,1424)}; print(r); print("largest success",max((n for n,v in r.items() if v),default=None)); print("smallest failure",min((n for n,v in r.items() if not v),default=None))'
h2 iperf3 -s -1 -J > /tmp/week6-mismatch-server.json 2>&1 &
sh sleep 1
h1 timeout 20s iperf3 -c 10.95.100.2 -t 5 -J
h2 cat /tmp/week6-mismatch-server.json
h2 ip -s link show h2-eth0
h2 ip -s link show vx100
h2 nstat -az
h2 ip link set h2-eth0 mtu 1500
h1 ping -c 3 10.95.100.2
exit
```

The strict predicted payload budget is `1400 - 50 - 28 = 1322`. Some Linux virtual receive paths may allow four additional bytes when comparing frame lengths, producing a boundary near 1326/1327. This is a hypothesis to test, not an observed result or a portable allowance. Report the measured adjacent success/failure and repeat it. Use baseline and final counters to identify drops; individual interfaces need not account for all stack drops. Small traffic can work while full TCP segments exceed the receive limit. Restore MTU even if a test fails; terminate only the iperf server you started if its one-off transfer never completes.

## Part 7 — Docker on the laptop host

Outside the course container, after Docker Desktop's Linux engine is healthy:

```bash
docker run --name week6-alpine --rm -d alpine sleep 300
docker exec week6-alpine ip -br link
docker exec week6-alpine cat /etc/os-release
docker exec week6-alpine ps
docker stop week6-alpine
docker ps -a --filter name=week6-alpine
```

`--rm` removes this temporary container after it stops. Docker provides a container filesystem/image, process and other namespace isolation, and resource controls as configured. A Mininet host is normally just a process with its own network namespace and shared host filesystem. Both use the host Linux kernel; neither is a full VM. Inspect only this lab container, not unrelated containers.

## D5 — Assignment collector

Inside the privileged course container with Python, PyYAML, Mininet, iproute2/bridge, ping, tcpdump, `timeout`, and iperf3:

```bash
python3 -m unittest discover -s tests -v
python3 build_overlay.py blackhole.yaml > evidence6/check.txt 2>&1
# The preceding command MUST fail before building anything.
python3 run_week6_experiments.py flood
python3 run_week6_experiments.py isolation
python3 run_week6_experiments.py blackhole
python3 run_week6_experiments.py fixes
python3 run_week6_experiments.py connectivity
```

Each collector action constructs and stops its own network. `blackhole` is equivalent to `python3 build_overlay.py blackhole.yaml --force`. It scans payloads 1400–1473 and reports measured successes and failures within that range. Extend the range if it does not bracket a stable boundary. It deliberately does not bypass structural validation. The original all-1500 YAML is byte-for-byte the initial design, recoverable from the design commit.

Flooding captures at willow while res1 on cedar communicates with res2 on maple. Isolation captures at art2 (`10.95.50.11`, studio) while research res1 contacts research res2 at the same address. The subsequent studio test checks its own separate neighbour mapping. Inspect the log for failures before continuing. The collector checks capture readiness, checks zero captured ARP/ICMP on the other tenant, and stops on unexpected errors. The live collector is syntax-checked but unverified on Mininet in this environment.

The connectivity collector tests every ordered same-tenant pair in a fresh network and writes `evidence6/connectivity.txt`. For interactive confirmation, use a fresh `python3 build_overlay.py overlay.yaml` CLI session to ping **every distinct ordered VM pair within each tenant** (res1/res2/res3/res4 at .10/.11/.12/.13; art1/art2/art3 at .10/.11/.12). This covers both same-hypervisor and remote paths. Never use overlapping-address `pingall`. Exit the CLI afterward. Full-mesh same-tenant testing and runtime isolation remain pending here.

MTU configurations:

| File | Tenant / underlay | Validation | Interpretation |
|---|---|---|---|
| blackhole.yaml | 1500 / 1500 | Reject by 50 bytes per tenant | Original faulty design; `--force` for investigation only |
| mtu_a.yaml | 1950 / 1500 | Reject by 500 bytes per tenant | Requested Fix A contradicts the stated safety rule |
| mtu_a_reduced.yaml | 1450 / 1500 | Pass | Valid reduced-MTU alternative; ping payloads 1422 and 1423 |
| mtu_b.yaml and overlay.yaml | 1500 / 9000 | Pass | Selected jumbo underlay; ping payloads 1472 and 1473 |

Fix B preserves guest MTU 1500 but requires every fabric port and path to carry at least 1550 IP bytes (9000 is the configured headroom). Corrected Fix A works with a conventional underlay but requires changing all guest/tenant interfaces and transports 50 fewer payload bytes per full IP packet. No throughput ranking is available until genuine measurements are obtained; software scheduling, CPU load, offloads and packet rate affect Mininet iperf results.

After collecting real output, revise the measurement-dependent answers in `page6.yaml` and the README, then regenerate and validate:

```bash
python3 make_page6.py overlay.yaml
python3 -m unittest discover -s tests -v
python3 -m py_compile build_overlay.py make_page6.py run_week6_experiments.py
```

## Technical references

The size accounting and encapsulation follow [RFC 7348](https://www.rfc-editor.org/rfc/rfc7348.html). Linux's static/dynamic VXLAN forwarding is described in the [kernel VXLAN documentation](https://www.kernel.org/doc/html/latest/networking/vxlan.html). [RFC 8365](https://www.rfc-editor.org/rfc/rfc8365.html) explains EVPN control-plane MAC/IP advertisements and remote learning. Linux receive tolerance and the missing lecture P4 program were not verified from these sources.
