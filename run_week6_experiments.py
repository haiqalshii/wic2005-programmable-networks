#!/usr/bin/env python3
"""D5 collector. Run as root INSIDE the isolated course container, from this repo.

Every session builds a new network and stops it in finally. No global mn -c.
Evidence records actual output, including dependency failures; never substitutes predictions.
"""
import contextlib
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import traceback

import build_overlay as overlay


def command(net, node, text):
    print(f'$ {node} {text}', flush=True)
    out, err, code = net.get(node).pexec('sh', '-c', text)
    print(out + err, end='' if (out + err).endswith('\n') else '\n', flush=True)
    print(f'[exit {code}]', flush=True)
    return code, out + err


@contextlib.contextmanager
def session(path, force=False):
    print(f'$ python3 build_overlay.py {path}' + (' --force' if force else ''), flush=True)
    spec = overlay.load(path)
    problems = overlay.problems_for(spec, force)
    if problems:
        for problem in problems:
            print('PROBLEM:', problem)
        raise RuntimeError('Design rejected; nothing built')
    if force:
        for problem in overlay.check_mtu(spec):
            print('WARNING: --force:', problem)
    if importlib.util.find_spec('mininet') is None:
        raise RuntimeError("BLOCKED: No module named 'mininet'; no network was constructed")
    if os.geteuid() != 0:
        raise RuntimeError('BLOCKED: root is required inside the privileged course container')
    missing = [p for p in ['ip', 'bridge', 'ping', 'tcpdump', 'iperf3', 'timeout'] if not shutil.which(p)]
    if missing:
        raise RuntimeError('BLOCKED: missing commands: ' + ', '.join(missing))
    net, _ = overlay.build(spec)
    try:
        print('Fresh network:', json.dumps(overlay.plan(spec), indent=2))
        yield net, spec
    finally:
        net.stop()
        print('Stopped this experiment network.', flush=True)


def ping(net, src, dst, size=56, required=False):
    status, out = command(net, src, f'ping -n -c 2 -W 1 -M do -s {size} {dst}')
    if required and status:
        raise RuntimeError(f'Unexpected connectivity failure: {src} -> {dst}; investigate before continuing')
    return status == 0


def throughput(net, src, dst, address):
    server = net.get(dst).popen(['iperf3', '-s', '-1', '-J'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(.4)
        code, out = command(net, src, f'timeout 20s iperf3 -c {address} -t 5 -J --connect-timeout 3000')
        if code == 0:
            result = json.loads(out)
            print('ACTUAL receiver throughput (bits/s):', result['end']['sum_received']['bits_per_second'])
        else:
            print('No successful receiver throughput measurement.')
        try:
            output, _ = server.communicate(timeout=10)
            print('Server JSON:\n' + output)
        except subprocess.TimeoutExpired:
            print('Server did not complete; stopping only this server.')
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.communicate()


@contextlib.contextmanager
def capture(net, node, interface, expression):
    proc = net.get(node).popen(['tcpdump', '-l', '-nn', '-e', '-vv', '-i', interface, expression],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(f'$ {node} tcpdump -l -nn -e -vv -i {interface} {shlex.quote(expression)}')
    result = {}
    try:
        # Allow libpcap setup; validate the listening message when collecting output.
        time.sleep(1)
        if proc.poll() is not None:
            raise RuntimeError('tcpdump exited before the experiment: ' + proc.communicate()[0])
        yield result
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        print(out, flush=True)
        if 'listening on' not in out:
            raise RuntimeError('Capture did not confirm a listening interface')
        result['text'] = out


def connectivity():
    with session('overlay.yaml') as (net, spec):
        addresses = overlay.plan(spec)['vms']
        for tenant in spec['tenants']:
            for source, _ in tenant['vms']:
                for destination, _ in tenant['vms']:
                    if source != destination:
                        ping(net, source, addresses[destination]['ip'], required=True)
        print('PASS: every ordered same-tenant VM pair communicated.')


def flood():
    with session('overlay.yaml') as (net, spec):
        for hv in spec['hypervisors']:
            command(net, hv, 'bridge fdb show dev vxlan9510')
        with capture(net, 'willow', 'willow-eth0', 'udp port 4789'):
            ping(net, 'res1', '10.95.50.11', required=True)
        for hv in spec['hypervisors']:
            command(net, hv, 'bridge fdb show dev vxlan9510')
            command(net, hv, 'bridge fdb show br br9510')


def isolation():
    with session('overlay.yaml') as (net, _):
        with capture(net, 'art2', 'art2-eth0', 'arp or icmp') as cap:
            ping(net, 'res1', '10.95.50.11', required=True)
        counts = re.findall(r'^(\d+) packets captured$', cap['text'], re.M)
        if counts != ['0']:
            raise RuntimeError('Isolation capture is inconclusive or contains unexpected packets; investigate')
        print('PASS: no ARP/ICMP reached the studio VM during research ping.')
        ping(net, 'art1', '10.95.50.11', required=True)
        for vm in ['res1', 'res2', 'art1', 'art2']:
            command(net, vm, 'ip neigh show; ip -br link')
        for hv in ['cedar', 'maple', 'willow']:
            command(net, hv, 'ip -d link show type vxlan; bridge link show')


def sizes(net, src, dst, low, high):
    outcomes = {size: ping(net, src, dst, size) for size in range(low, high + 1)}
    ok = [size for size, success in outcomes.items() if success]
    fail = [size for size, success in outcomes.items() if not success]
    print('Measured maximum success in scanned range:', max(ok) if ok else 'none')
    print('Measured minimum failure in scanned range:', min(fail) if fail else 'none')
    print('Scan range:', low, high, '(not a universal limit if failures are non-monotonic)')


def blackhole():
    with session('blackhole.yaml', force=True) as (net, _):
        ping(net, 'res1', '10.95.50.11', required=True)
        sizes(net, 'res1', '10.95.50.11', 1400, 1473)
        throughput(net, 'res1', 'res2', '10.95.50.11')
        for hv in ['cedar', 'maple']:
            command(net, hv, f'ip -s link show {hv}-eth0; ip -s link show vxlan9510')


def fixes():
    print('Requested Fix A is tested as specified, without bypassing validation:')
    for problem in overlay.problems_for(overlay.load('mtu_a.yaml'), False):
        print('PROBLEM:', problem)
    print('It is invalid; only the corrected reduced-MTU alternative and Fix B are built below.')
    for path, payloads in [('mtu_a_reduced.yaml', (1422, 1423)), ('mtu_b.yaml', (1472, 1473))]:
        with session(path) as (net, _):
            ping(net, 'res1', '10.95.50.11', required=True)
            ping(net, 'res1', '10.95.50.11', payloads[0], required=True)
            if ping(net, 'res1', '10.95.50.11', payloads[1]):
                raise RuntimeError('Unexpected success beyond VM MTU; investigate offload/settings')
            throughput(net, 'res1', 'res2', '10.95.50.11')


def main():
    actions = {'flood': flood, 'isolation': isolation, 'blackhole': blackhole, 'fixes': fixes, 'connectivity': connectivity}
    names = sys.argv[1:] or list(actions)
    if any(name not in actions for name in names):
        sys.exit('usage: python3 run_week6_experiments.py [flood isolation blackhole fixes connectivity]')
    Path('evidence6').mkdir(exist_ok=True)
    for name in names:
        with open(f'evidence6/{name}.txt', 'w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            print('Recorded UTC:', datetime.datetime.now(datetime.timezone.utc).isoformat())
            print('Collector:', name, flush=True)
            try:
                actions[name]()
            except Exception:
                traceback.print_exc()
                print('INCOMPLETE: no successful live experiment is claimed.')
                # Stop on unexpected execution failures. Dependency blocks can be recorded per experiment.
                if importlib.util.find_spec('mininet') is not None:
                    return 1
        print(f'Wrote evidence6/{name}.txt (inspect status inside file).')
    return 0 if importlib.util.find_spec('mininet') is not None else 1


if __name__ == '__main__':
    sys.exit(main())
