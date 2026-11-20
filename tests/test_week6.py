"""Pure validation tests; these do not simulate or claim live packet delivery."""
import copy
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_overlay as overlay


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.spec = overlay.load('overlay.yaml')

    def test_design_variants(self):
        for path, excess in [('overlay.yaml', 0), ('mtu_b.yaml', 0),
                             ('mtu_a_reduced.yaml', 0), ('blackhole.yaml', 50),
                             ('mtu_a.yaml', 500)]:
            with self.subTest(path=path):
                spec = overlay.load(path)
                self.assertEqual(overlay.check_spec(spec), [])
                problems = overlay.check_mtu(spec)
                self.assertEqual(len(problems), 2 if excess else 0)
                for problem in problems:
                    self.assertIn(f'by {excess} bytes', problem)

    def test_mtu_exact_boundary_and_one_byte_over(self):
        self.spec['underlay']['mtu'] = 1550
        self.assertEqual(overlay.check_mtu(self.spec), [])
        self.spec['tenants'][0]['mtu'] += 1
        problems = overlay.check_mtu(self.spec)
        self.assertEqual(len(problems), 1)
        self.assertIn('research', problems[0])
        self.assertIn('by 1 bytes', problems[0])

    def test_addresses_macs_and_overlap(self):
        p = overlay.plan(self.spec)
        self.assertEqual(p['hypervisors'], dict(cedar='10.95.0.1', maple='10.95.0.2', willow='10.95.0.3'))
        self.assertEqual(p['vms']['res2']['ip'], p['vms']['art2']['ip'])
        self.assertEqual(p['vms']['res2']['mac'], '02:00:25:26:00:0b')
        self.assertEqual(len({v['mac'] for v in p['vms'].values()}), 7)

    def test_membership_and_flood_peers(self):
        addresses = overlay.plan(self.spec)['hypervisors']
        for hv in self.spec['hypervisors']:
            for tenant in self.spec['tenants']:
                cmds = overlay.tenant_commands(self.spec, hv, tenant)
                local = [vm for vm, host in tenant['vms'] if host == hv]
                if not local:
                    self.assertEqual(cmds, [])
                    continue
                vni = tenant['vni']
                self.assertEqual(cmds[0], f'ip link add br{vni} type bridge')
                vx = next(c for c in cmds if 'type vxlan' in c)
                self.assertIn(f'local {addresses[hv]} dstport 4789 dev {hv}-eth0', vx)
                self.assertNotIn('remote', vx)
                expected = {f'bridge fdb append 00:00:00:00:00:00 dev vxlan{vni} dst {addresses[peer]}'
                            for _, peer in tenant['vms'] if peer != hv}
                actual = [c for c in cmds if c.startswith('bridge fdb append')]
                self.assertEqual(set(actual), expected)
                self.assertEqual(len(actual), len(expected))
                ports = overlay.vm_ports(self.spec, hv)
                for vm, port in ports.items():
                    membership = f'ip link set {port} master br{vni}'
                    self.assertEqual(membership in cmds, vm in local)
                self.assertIn(f'ip link set vxlan{vni} mtu 1500 up', cmds)

    def test_generalised_renamed_design(self):
        spec = copy.deepcopy(self.spec)
        rename = {'cedar': 'oak', 'maple': 'birch', 'willow': 'elm'}
        spec['hypervisors'] = [rename[h] for h in spec['hypervisors']]
        spec['underlay']['network'] = '10.95.8.0/24'
        for i, tenant in enumerate(spec['tenants']):
            tenant['vni'] = 100000 + i
            tenant['mtu'] = 1400
            tenant['vms'] = [[f'n{i}{j}', rename[h]] for j, (_, h) in enumerate(tenant['vms'])]
        self.assertEqual(overlay.check_spec(spec), [])
        commands = overlay.all_commands(spec)
        self.assertIn('ip link add vxlan100000 type vxlan id 100000 local 10.95.8.1 dstport 4789 dev oak-eth0', commands['oak'])
        self.assertIn('ip link set vxlan100001 mtu 1400 up', commands['elm'])
        self.assertIn('bridge fdb append 00:00:00:00:00:00 dev vxlan100001 dst 10.95.8.3', commands['oak'])

    def test_force_bypasses_only_mtu(self):
        spec = overlay.load('blackhole.yaml')
        self.assertEqual(overlay.problems_for(spec, True), [])
        spec['tenants'][1]['vni'] = spec['tenants'][0]['vni']
        self.assertTrue(overlay.problems_for(spec, True))

    def test_rejection_precedes_mininet_import(self):
        result = subprocess.run([sys.executable, 'build_overlay.py', 'blackhole.yaml'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count('PROBLEM:'), 2)
        self.assertIn('nothing was built', result.stderr)
        self.assertNotIn('mininet', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
