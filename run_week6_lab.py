#!/usr/bin/env python3
"""Parts 1–6; run only in a disposable privileged course container."""
import contextlib
import datetime
import subprocess
from mininet.net import Mininet
from mininet.nodelib import LinuxBridge
from run_week6_experiments import command, capture, ping, sizes, throughput
from build_overlay import NO_OFFLOAD
import shlex


def host(cmd):
    print('$', cmd, flush=True)
    result = subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, '[exit', result.returncode, ']', flush=True)
    if result.returncode:
        raise RuntimeError(cmd)


def main():
    print('Actual lab output UTC:', datetime.datetime.now(datetime.timezone.utc).isoformat())
    net = Mininet(controller=None, switch=LinuxBridge, ipBase='10.95.0.0/24')
    try:
        sw = net.addSwitch('s1')
        for name in ['h1', 'h2']:
            net.addLink(net.addHost(name), sw)
        net.start()
        print('PART 1: processes, namespaces and veth peers')
        host('lsns -t net -o NS,TYPE,NPROCS,PID,COMMAND')
        host('ip -br link')
        for h in net.hosts:
            print('Mininet host shell PID:', h.name, h.pid)
            command(net, h.name, 'ip -br link; ip -o link; readlink /proc/self/ns/net')
        ping(net, 'h1', '10.95.0.2', required=True)
    finally:
        net.stop()

    print('PART 2: manually created namespaces')
    # This script owns all objects below, inside a fresh disposable container.
    try:
        for cmd in ['ip netns add red', 'ip netns add blue',
                    'ip link add red0 type veth peer name redbr',
                    'ip link add blue0 type veth peer name bluebr',
                    'ip link set red0 netns red', 'ip link set blue0 netns blue',
                    'ip link add br0 type bridge', 'ip link set redbr master br0',
                    'ip link set bluebr master br0', 'ip link set br0 up',
                    'ip link set redbr up', 'ip link set bluebr up',
                    'ip -n red link set lo up', 'ip -n blue link set lo up',
                    'ip -n red addr add 10.95.9.1/24 dev red0',
                    'ip -n blue addr add 10.95.9.2/24 dev blue0',
                    'ip -n red link set red0 up', 'ip -n blue link set blue0 up',
                    'ip netns exec red ping -c 3 10.95.9.2', 'bridge fdb show br br0']:
            host(cmd)
    finally:
        for cmd in ['ip netns del red', 'ip netns del blue', 'ip link del br0']:
            host(cmd)

    net = Mininet(controller=None, switch=LinuxBridge, ipBase='10.95.0.0/24')
    try:
        sw = net.addSwitch('s1')
        for name in ['h1', 'h2']:
            net.addLink(net.addHost(name), sw)
        net.start()
        print('PARTS 3–4: IPv4 VXLAN and throughput')
        for n, peer in [(1, 2), (2, 1)]:
            name = f'h{n}'
            # Kernel enforces creation MTU; lower the underlay after setup.
            for cmd in [f'ip link set {name}-eth0 mtu 2000',
                        f'ip link add vx100 type vxlan id 100 local 10.95.0.{n} remote 10.95.0.{peer} dstport 4789 dev {name}-eth0',
                        f'ip addr add 10.95.100.{n}/24 dev vx100',
                        'ip link set vx100 mtu 1950 up',
                        f'ip link set {name}-eth0 mtu 1500',
                        f'python3 -c {shlex.quote(NO_OFFLOAD)} {name}-eth0 vx100',
                        f'ip -d link show vx100; ip link show {name}-eth0']:
                code, _ = command(net, name, cmd)
                if code:
                    raise RuntimeError(cmd)
        with capture(net, 'h2', 'h2-eth0', 'udp port 4789'):
            ping(net, 'h1', '10.95.100.2', required=True)
            ping(net, 'h1', '10.95.100.2', 1422)
            ping(net, 'h1', '10.95.100.2', 1423)
        print('UNDERLAY THROUGHPUT')
        throughput(net, 'h1', 'h2', '10.95.0.2')
        print('OVERLAY THROUGHPUT')
        throughput(net, 'h1', 'h2', '10.95.100.2')
        print('PART 5: IPv6 underlay')
        for n, peer in [(1, 2), (2, 1)]:
            for cmd in [f'ip -6 addr add fd00:1995::{n}/64 dev h{n}-eth0 nodad',
                        f'ip link add vx106 type vxlan id 106 local fd00:1995::{n} remote fd00:1995::{peer} dstport 4789 dev h{n}-eth0',
                        f'ip addr add 10.95.106.{n}/24 dev vx106',
                        'ip -d link show vx106', 'ip link set vx106 mtu 1430 up']:
                code, _ = command(net, f'h{n}', cmd)
                if code:
                    raise RuntimeError(cmd)
        command(net, 'h1', 'ping -6 -c 3 fd00:1995::2')
        ping(net, 'h1', '10.95.106.2', required=True)
        ping(net, 'h1', '10.95.106.2', 1402)
        ping(net, 'h1', '10.95.106.2', 1403)
        print('PART 6: receiving-underlay MTU 1400')
        command(net, 'h2', 'ip link set h2-eth0 mtu 1400; ip -s link show h2-eth0; nstat -az')
        try:
            ping(net, 'h1', '10.95.100.2', required=True)
            ping(net, 'h1', '10.95.100.2', 1422)
            sizes(net, 'h1', '10.95.100.2', 1318, 1332)
            throughput(net, 'h1', 'h2', '10.95.100.2')
            command(net, 'h2', 'ip -s link show h2-eth0; ip -s link show vx100; nstat -az')
        finally:
            command(net, 'h2', 'ip link set h2-eth0 mtu 1500')
        ping(net, 'h1', '10.95.100.2', required=True)
    finally:
        net.stop()


if __name__ == '__main__':
    with open('evidence6/lab.txt', 'w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        main()
