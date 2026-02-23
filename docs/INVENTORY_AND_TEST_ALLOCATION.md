# Inventory and Test Allocation Design

How to scale the inventory to more routers (3–4+) and allocate tests so that multi-node tests have enough nodes and tests do not interfere with each other.

---

## 1. Inventory layout: groups by topology size

Use **groups** so playbooks can target “any 2 routers,” “any 4 routers,” or a fixed pod.

### Recommended group structure

```ini
# hosts (or inventory file)

[vyos_hosts]
r1 ansible_ssh_host=192.0.2.21
r2 ansible_ssh_host=192.0.2.22
r3 ansible_ssh_host=192.0.2.23
r4 ansible_ssh_host=192.0.2.24

# Fixed pairs for 2-node tests (no overlap between pair_1 and pair_2)
[pair_1]
r1
r2

[pair_2]
r3
r4

# For 3-node tests (e.g. route reflector + 2 clients, or DHCP relay path)
[triple_1]
r1
r2
r3

# For 4-node tests (e.g. VRRP + real servers, BGP RR + 3 clients, EVPN)
[quad]
r1
r2
r3
r4

# Optional: by role for clarity (same hosts, different view)
[tunnel_endpoints_1]
r1
r2
[tunnel_endpoints_2]
r3
r4
```

- **vyos_hosts**: all DUTs (for single-node tests or when you want “run on all”).
- **pair_1 / pair_2**: two disjoint 2-node sets so two 2-node tests can run in parallel (different playbooks/limits) or sequentially without sharing state.
- **triple_1**: one 3-node set for tests that need exactly 3 routers.
- **quad**: one 4-node set for tests that need 4 routers.

Add more groups (e.g. `pair_3`, `triple_2`) if you add more hosts and want more isolation.

---

## 2. Test-to-topology mapping (how many routers)

| Min routers | Typical tests | Examples |
|-------------|----------------|----------|
| **1** | Single-node config + show | BOND-001, BRIDGE-001, DUMMY-001, PETH-001, VETH-001, WG-002, WLAN-001, WWAN-001, most system/service tests |
| **2** | Tunnels, VPN, ping reachability | TUN-001, VXLAN-001, GENEVE-001, VTI-001, WG-001, OVPN-001, L2TPV3-001, SSTP-001, PPPOE-001, ETH-001/002, DUMMY-001 (ping), LOOP-001 (ping), FW-GROUP-001/002 (traffic from peer) |
| **3** | Route reflector, relay path, BFD/three-way | BGP-002 (RR + 2 clients), SVC-DHCPR-001 (client relay server), BFD multihop, optional OSPF/ISIS multi-area |
| **4** | HA, load balance, EVPN, full mesh | HA-VRRP-001/002 (2× VRRP pairs or 2 routers + 2 reals), HA-VS-001/002 (LB + reals), BGP-003 (EVPN), BGP-002 (RR + 3 clients), config-sync/conntrack-sync (2 pairs) |

So:

- **1-node**: run on `vyos_hosts` (or a subset); each host runs the test independently.
- **2-node**: run on `pair_1` or `pair_2` (or a variable like `rv_pair`).
- **3-node**: run on `triple_1`.
- **4-node**: run on `quad`.

---

## 3. Smart allocation: avoid interference

Three levers: **spatial** (different routers), **logical** (different names/prefixes per test), **temporal** (order + cleanup).

### 3.1 Spatial: different groups for different test “kinds”

- Use **pair_1** for one set of 2-node tests (e.g. all tunnel tests that need connectivity).
- Use **pair_2** for another set (e.g. firewall + traffic-from-peer tests), or for a second run of the same tests.
- Use **quad** only for 4-node tests so 2-node tests don’t touch the same four routers at once if you want a clean 4-node lab.

This way, 2-node tests on pair_1 don’t share interfaces/addresses with tests on pair_2.

### 3.2 Logical: per-test (or per-pod) namespaces

So that tests don’t clash even when they run on the same routers (e.g. sequentially on pair_1):

- **Interface names**: derive from test ID or a stable suffix, not a single global name.
  - Examples: bond for BOND-001 → `bond_rv_001` or `bond_pod1`; bridge → `br_rv_001`; tunnel → `tun_rv_tun001`; VXLAN → `vxlan_rv_001`.
  - Avoid reusing the same name (e.g. `bond0`, `br0`) across tests unless you always cleanup before the next test.
- **IP addressing**: one subnet (or block) per test or per test category.
  - Example scheme: base `10.<test_index>.0.0/24` or use the CSV row (e.g. test 1 → 192.0.2.0/24, test 7 → 192.0.2.6.0/24). For tunnels/overlays use a dedicated range (e.g. 198.51.100.0/24 for TUN-001, 198.51.101.0/24 for VXLAN-001).
  - Ensures no overlap between BOND-001’s address and TUN-001’s tunnel IPs when both run on the same host.
- **Firewall / policy names**: include test ID or pod (e.g. `rv_fw_001`, `rv_br_fw_pod1`).

Result: same routers can run many tests one after another without address or name collisions if each task uses its own namespace.

### 3.3 Temporal: order and cleanup (smoketest-style)

Release verification follows the **existing smoketest pattern**: cleanup after every test (like `tearDown()` in unittest). Each test uses a **block** with **always** so cleanup runs even when the test fails.

- Run tests in a **defined order** (e.g. by test_case_id or by category).
- **Cleanup is the default**; use `--skip-tags cleanup` only when you want to leave config for inspection.
- For 2-node tests: configure **both** endpoints first (e.g. tunnel on r1 and r2), then run connectivity check (e.g. ping from r2 to r1’s overlay IP), then cleanup **both** before the next test.

That way, even on the same pair, TUN-001’s tunnel and addresses are removed before VXLAN-001 runs.

---

## 4. Host vars: who is my peer / which pod

Each host should know its “partner(s)” and addressing for multi-node tests so tasks don’t hardcode r1/r2.

Suggested pattern (per host):

```yaml
# host_vars/r1.yml (conceptually)
# For 2-node tests on pair_1
rv_pair: pair_1
rv_peer: r2
rv_my_index: 1   # or 0 for “first” in pair

# Addressing for this host (used by tests)
rv_underlay_ip: 10.0.2.11
rv_underlay_prefix: 24
rv_dummy_ip: 203.0.113.11
# Optional: overlay ranges for tunnel tests
rv_tunnel_overlay_ip: 198.51.100.1
rv_tunnel_overlay_prefix: 24
```

```yaml
# host_vars/r2.yml
rv_pair: pair_1
rv_peer: r1
rv_my_index: 2
rv_underlay_ip: 10.0.2.14
rv_dummy_ip: 203.0.113.14
rv_tunnel_overlay_ip: 198.51.100.2
```

Then in tasks:

- “Configure tunnel local=my underlay, remote=peer’s underlay” using `hostvars[rv_peer]`.
- “Ping from this host to peer’s overlay” using `hostvars[rv_peer].rv_tunnel_overlay_ip`.

For **quad**, add vars like `rv_quad_role: spine | leaf | rr | client` and `rv_quad_peers: [r2, r3]` as needed so 4-node tests know who configures what.

---

## 5. Playbook strategy: how to “allocate” tests to groups

**Option A – Single playbook, limit by group**

- One playbook (e.g. `release_verification.yml`) that includes all tests.
- Run 2-node tests with: `ansible-playbook release_verification.yml -l pair_1 --tags "2node"`.
- Run 4-node tests with: `ansible-playbook release_verification.yml -l quad --tags "4node"`.
- Run single-node tests with: `ansible-playbook release_verification.yml -l vyos_hosts --tags "1node"` (or no limit and use `when` so 2/4-node tests skip when not in the right group).

**Option B – Separate playbooks per topology**

- `release_verification_1node.yml` → hosts: vyos_hosts.
- `release_verification_2node.yml` → hosts: "{{ rv_pair_group | default('pair_1') }}".
- `release_verification_4node.yml` → hosts: quad.

Then allocate by choosing which playbook to run (and optionally which group, e.g. `pair_2`).

**Option C – Mixed (recommended)**

- One playbook, multiple plays:
  - Play 1: hosts: vyos_hosts, role: release_verification, tags: 1node (single-node tasks only).
  - Play 2: hosts: "{{ rv_2node_group | default('pair_1') }}", role: release_verification, tags: 2node (two-node config + connectivity).
  - Play 3: hosts: quad, role: release_verification, tags: 4node (four-node only).
- Run all: `ansible-playbook release_verification.yml`.
- Run only 2-node: `ansible-playbook release_verification.yml --tags 2node`.
- Run on second pair: `ansible-playbook release_verification.yml -e rv_2node_group=pair_2 --tags 2node`.

Allocation is then “by play + tag + group,” and you can add `triple_1` later for 3-node tests.

---

## 6. Summary: best approach

1. **Inventory**: Define `vyos_hosts`, `pair_1`, `pair_2`, `triple_1`, `quad` (and more pairs/triples if you add routers). Keep group membership explicit so “which routers for 2-node” is clear.
2. **Allocation**:  
   - 1-node tests → any host(s) in `vyos_hosts`.  
   - 2-node tests → `pair_1` or `pair_2` (or a variable).  
   - 3-node → `triple_1`.  
   - 4-node → `quad`.
3. **No interference**:  
   - **Spatial**: Use different groups for parallel or unrelated test runs (e.g. pair_1 for tunnels, pair_2 for firewall).  
   - **Logical**: Per-test (or per-pod) interface names and IP subnets; avoid reusing the same bond/bridge/tunnel/firewall names and prefixes across tests.  
   - **Temporal**: Run in order and run cleanup after each test (or test group) so the next test starts from a clean state.
4. **Host vars**: Store `rv_peer`, `rv_underlay_ip`, `rv_tunnel_overlay_ip`, and optionally pod/quad role so tasks can target “the other router” and correct IPs without hardcoding r1/r2.
5. **Playbooks**: Prefer one playbook with plays (or includes) per topology (1-node / 2-node / 4-node) and tags, and use `-l` / `-e rv_2node_group=...` to choose which routers run which tests.

This gives a scalable, clear way to add more routers and run 2-, 3-, and 4-node tests without interference.
