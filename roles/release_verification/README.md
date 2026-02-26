# Release verification role

Ansible role implementing the VyOS release verification test suite. Covers 209 test cases across 19 categories; 31 implemented so far.

## Directory structure

```
roles/release_verification/
  tasks/
    main.yml                  # imports category mains
    _helpers/                 # shared reusable task patterns
      ping_peer.yml               # ping + assert 0% packet loss
      show_assert.yml             # show command + assert string
      wait_route.yml              # retry loop for route convergence
      wait_for_eth1_underlay.yml  # poll eth1 until rv_underlay_ip is active
    interfaces/               # 22 tests implemented
      main.yml
      bond_001.yml ... wwan_001.yml
      bond_001.md  ... wwan_001.md   # per-test command/assertion docs
    firewall/                 # 4 tests implemented
      main.yml
      fw_global_001.yml ... fw_group_003.yml
    nat/ protocols/ policy/ service/ system/ qos/ vpn/ ha/
    loadbalancing/ container/ pki/ vrf/ vpp/ operation/ cli/
    install/ migration/       # placeholder main.yml only
  vars/
    main.yml                  # auto-loaded role vars (organized by category)
    test_registry.yml         # metadata for all 207 tests (not auto-loaded)
```

## Conventions

### Test file header

Every test file starts with a structured comment block:

```yaml
---
# TEST-ID: Short description
# Topology: 2-node symmetric | 2-node asymmetric | 1-node
#   r1: what r1 does
#   r2: what r2 does
```

For single-node tests, omit the r1/r2 lines. For asymmetric tests (client/server), describe each role clearly.

### Test isolation (block/always)

Every test that modifies config uses `block/always` for cleanup:

```yaml
- block:
    - name: TEST - Configure ...
    - name: TEST - Verify ...
    - name: TEST - Assert ...
  always:
    - name: TEST - Cleanup ...
      ignore_errors: true
```

No resource reuse between tests. Each test sets up everything it needs and tears it down completely.

### Underlay setup for 2-node tests

Most 2-node tests need IP connectivity on eth1. Each test configures its own underlay and removes it:

```yaml
# First task in block:
- name: TEST - Set up eth1 underlay IP
  vyos.vyos.vyos_config:
    lines:
      - "set interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'"

# Last task in always:
- name: TEST - Remove eth1 underlay IP
  vyos.vyos.vyos_config:
    lines:
      - "delete interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'"
  ignore_errors: true
```

Tests that assign their own IP on eth1 (e.g. ETH-001 uses `rv_eth_test_ip`) don't need this — they manage eth1 directly.

### Asymmetric (client/server) tests

When routers have different roles, use `inventory_hostname` conditionals:

```yaml
- name: DHCP-001 - Configure server (r1)
  vyos.vyos.vyos_config:
    lines: [...]
  when: inventory_hostname == 'r1'

- name: DHCP-001 - Configure client (r2)
  vyos.vyos.vyos_config:
    lines: [...]
  when: inventory_hostname == 'r2'
```

Do not use role variables for this. Keep it simple with `inventory_hostname`.

### Ping assertions

Use `deadline` (not `timeout`) for the VyOS ping command. Assert with a leading comma to avoid false positives where `100% packet loss` contains `0% packet loss`:

```yaml
commands:
  - "ping {{ target }} count 3 deadline 10"
# ...
assert:
  that:
    - "', 0% packet loss' in result.stdout[0]"
```

### OSPF convergence

For tests that need OSPF route propagation (DUMMY-001, LOOP-001), use a retry loop instead of a fixed sleep:

```yaml
- name: Wait for OSPF to learn route
  vyos.vyos.vyos_command:
    commands:
      - "show ip route {{ target_ip }}"
  register: route_result
  until: target_ip in route_result.stdout[0]
  retries: 12
  delay: 5
```

Each OSPF test must set up its own `protocols ospf area 0 network` and `redistribute connected`, then clean them up.

### Per-test documentation

Every `.yml` test file has a companion `.md` file in the same directory documenting:
- Commands executed
- Verification commands
- Assertions checked
- Cleanup commands

### Tags

Every task has tags: `[TEST-ID, category, subcategory]`. Cleanup tasks add `cleanup`.

```bash
--tags interfaces              # one category
--tags BOND-001                # one test
--tags "firewall,nat"          # multiple categories
--tags cleanup                 # cleanup tasks only
```

## Inventory and IP allocation

### Hosts

```
[vyos_hosts]
r1 ansible_host=192.168.124.40
r2 ansible_host=192.168.124.41
r3 ansible_host=192.168.124.42

[pair_1]
r1
r2

[trio_1]
r1
r2
r3
```

Run pair tests with `-l pair_1`, trio tests with `-l trio_1`. r3 is not defined in pair_1 and should not run 2-node pair tests.

### IP scheme (group_vars/vyos_hosts/ip.yml)

| Variable | r1 | r2 | r3 | Purpose |
|----------|-----|-----|-----|---------|
| eth0_ip | 192.168.124.40 | 192.168.124.41 | 192.168.124.42 | Management / SSH (ProxyJump via tests host) |
| eth1_ip | 10.0.2.1 | 10.0.2.2 | 10.0.3.3 | Test traffic (r1↔r2 on eth1, r3 on r2's eth2 side) |
| eth2_ip | — | 10.0.3.2 | — | r2's second leg towards r3 (trio tests) |
| dum0_ip | 203.0.113.11 | 203.0.113.14 | 203.0.113.17 | Dummy interface IPs |

### Interface allocation (vars/main.yml)

- `rv_eth_mgmt: "eth0"` — management, never touched by tests
- `rv_eth_test_interfaces: ["eth1", "eth2", "eth3"]` — available for tests

### Per-host overlay IPs (host_vars/r1.yml, r2.yml)

Each tunnel/overlay type gets its own IP pair so tests don't conflict:

| Variable | r1 | r2 |
|----------|-----|-----|
| rv_eth_test_ip | 10.30.0.1 | 10.30.0.2 |
| rv_vlan_test_ip | 10.100.0.1 | 10.100.0.2 |
| rv_tunnel_overlay_ip | 198.51.100.1 | 198.51.100.2 |
| rv_geneve_overlay_ip | 198.51.110.1 | 198.51.110.2 |
| rv_l2tpv3_overlay_ip | 198.51.111.1 | 198.51.111.2 |
| rv_vti_overlay_ip | 198.51.112.1 | 198.51.112.2 |
| rv_vxlan_overlay_ip | 198.51.120.1 | 198.51.120.2 |
| rv_wg_overlay_ip | 10.10.10.1 | 10.10.10.2 |
| rv_loop_test_ip | 192.0.2.201 | 192.0.2.202 |

## Development guidelines

Rules to follow when creating or modifying tests. Non-negotiable — these prevent regressions and keep the suite maintainable at 207+ tests.

### 1. Keep `.md` docs in sync with `.yml` tests

Every `.yml` test file has a companion `.md` in the same directory. When you change a test, **update its `.md` immediately** — commands, assertions, cleanup, topology, and any notes. Stale docs are worse than no docs.

### 2. Use shared helpers — never inline standard patterns

| Pattern | Helper | When to use |
|---------|--------|-------------|
| Ping + assert 0% loss | `_helpers/ping_peer.yml` | Every 2-node connectivity check |
| Route convergence wait | `_helpers/wait_route.yml` | OSPF/BGP route propagation |
| Show + assert string | `_helpers/show_assert.yml` | Simple single-string show checks |

```yaml
- import_tasks: ../_helpers/ping_peer.yml
  vars:
    _ping_target: "{{ hostvars[rv_peer].rv_overlay_ip }}"
    _ping_test_id: "TEST-001"
  when: rv_peer is defined
  tags: [TEST-001, category, 2node]
```

Guard the `import_tasks` with `when:` — do **not** add conditions inside the helper.

### 3. Every test file must have a topology header

```yaml
---
# TEST-ID: Short description
# Topology: 2-node symmetric | 2-node asymmetric | 1-node
#   r1: what r1 does
#   r2: what r2 does (omit for 1-node)
```

This is the first thing someone reads. Keep it accurate.

### 4. Use `block/always` for every test that modifies config

No exceptions. Even if cleanup is a single `delete` command. Tests must be self-contained and leave the router clean for the next test.

### 5. Never touch eth0 (management)

`eth0` is the SSH/management interface. Tests must only use `rv_eth_test_interfaces` (`eth1`, `eth2`, `eth3`). Breaking eth0 kills the Ansible connection mid-run.

### 6. Self-contained underlay setup per 2-node test

Each 2-node test configures `eth1` with `rv_underlay_ip` at the start and removes it in `always`. Do not assume eth1 has an IP from a previous test.

### 6a. Guard every pair test block with `when: inventory_hostname in groups['pair_1']`

r3 is in `[vyos_hosts]` but not in `[pair_1]`. `vyos.vyos` network modules resolve template variables before Ansible evaluates `when:` conditions on individual tasks, so a missing `rv_underlay_ip` (or any pair-only variable) on r3 would fail even if you only run `--tags SOME-TEST`. The solution is two-part:

1. Every `rv_*` pair variable must have a stub value in `host_vars/r3.yml` (so template resolution never errors).
2. Every pair test block must have `when: inventory_hostname in groups['pair_1']` at the block level so r3 is cleanly skipped.

```yaml
- block:
    - name: TEST-001 - ...
      ...
  always:
    - name: TEST-001 - Cleanup ...
      ...
  when: inventory_hostname in groups['pair_1']
```

Trio tests (`fw_ipv4_002.yml` and future trio tests) use per-task `when: inventory_hostname == 'r1'` conditionals instead — do **not** add the `pair_1` guard to them.

### 7. Use `deadline` (not `timeout`) for VyOS ping

VyOS `ping` uses `deadline` for the max-wait parameter. Check the CLI syntax notes table below before using any command.

### 8. Ping assertion must use leading comma

```yaml
- "', 0% packet loss' in result.stdout[0]"
```

Without the comma, `100% packet loss` matches `0% packet loss` — a silent false-positive.

### 9. Tag every task

Format: `[TEST-ID, category, subcategory]`. Add `cleanup` for cleanup tasks, `2node`/`1node` for topology-specific tasks. This enables selective test runs.

### 10. Verify CLI syntax against the table below

Before writing any VyOS command, check the **VyOS CLI syntax notes** table. When you discover a new syntax difference, add it to the table.

### 11. Graceful skip for hardware-dependent tests

Tests requiring physical hardware (WLAN, WWAN, etc.) must `ignore_errors` on the initial show command and emit a `SKIPPED` debug message if the hardware is absent. Never hard-fail for missing hardware.

### 12. Add new overlay IPs to host_vars when adding tunnel tests

Every tunnel/overlay type needs a unique IP pair in `host_vars/r1.yml` and `host_vars/r2.yml`. Never reuse another test's overlay subnet.

### 13. Do not duplicate VyOS unit tests — complement them

Before writing a test, check the VyOS smoketest suite (`vyos-1x/smoketest/scripts/cli/`) for the relevant feature. Unit tests verify **CLI → kernel/nftables translation** (synthetic, no real traffic). Our tests must go further:

| What unit tests cover | What we must add |
|-----------------------|-----------------|
| Config produces correct nftables/kernel state | Real traffic flows through the feature on live routers |
| CLI validates (commit succeeds) | Two routers can interoperate using the configured feature |
| Feature is syntactically correct | Feature survives a complete setup → verify → teardown cycle |

If a unit test already runs `ping` or `curl` through the feature, look for a gap in topology (e.g., unit test is single-node, we can add a 2-node interop variant). If there is genuinely nothing to add beyond what unit tests cover, skip the test and document why.

Add a comment block to every test file explaining what the unit test covers and what this test adds:

```yaml
# VyOS unit tests (smoketest/scripts/cli/test_xxx.py) already cover:
#   - <what they test>
#
# This test adds what unit tests cannot cover:
#   - <end-to-end / traffic / interop angle>
```

## VyOS CLI syntax notes

Current VyOS (rolling 2026) syntax differs from some older documentation:

| Feature | Correct syntax | Wrong/old syntax |
|---------|---------------|-----------------|
| Tunnel source | `source-address` | `local` |
| WireGuard listen port | `port` | `listen-port` |
| WireGuard peer key | `public-key` | `pubkey` |
| GENEVE interface name | `gnvN` (e.g. `gnv0`) | `geneveN` |
| Ping deadline | `deadline` | `timeout` |
| MACsec | `set interfaces macsec macsecN` | not under `ethernet` |
| SSTP client | `set interfaces sstpc sstpcN` | `sstp-client` |
| Bridge firewall | `set firewall bridge forward filter` | under `interfaces bridge` |
| OpenVPN site-to-site | TLS with `tls certificate` + `tls peer-fingerprint` | `shared-secret-key` (deprecated, BF-CBC crash) |
| FW global options | `show configuration commands \| grep global-options` | `show firewall` |
| IPv6 FW rule source group | `source group address-group 'NAME'` (under `firewall ipv6`) | `source group ipv6-address-group 'NAME'` |

## VTI note

VTI interfaces require an IPsec Security Association to forward traffic. VTI-001 is config-only (verifies interface creation). Full IPsec + VTI data-plane testing belongs in a dedicated VPN/IPsec test.

## Progress

| Category | Total | Done | Topology mix |
|----------|-------|------|-------------|
| interfaces | 22 | **22** | 10 pair, 5 single, 7 special |
| firewall | 11 | **9** | 6 pair, 3 trio |
| nat | 5 | 0 | pair |
| protocols | 22 | 0 | mostly pair, some quad |
| policy | 8 | 0 | mostly single |
| service | 26 | 0 | mixed |
| system | 28 | 0 | mostly single |
| qos | 8 | 0 | single |
| vpn | 9 | 0 | mostly pair |
| ha | 7 | 0 | pair |
| loadbalancing | 2 | 0 | mixed |
| container | 3 | 0 | single |
| pki | 5 | 0 | single |
| vrf | 5 | 0 | mostly pair |
| vpp | 19 | 0 | mixed |
| operation | 5 | 0 | single |
| cli | 7 | 0 | single |
| install | 7 | 0 | single |
| migration | 4 | 0 | single |
| **Total** | **209** | **31** | |

## Run

```bash
ansible-playbook release_verification.yml                       # all tests
ansible-playbook release_verification.yml --tags interfaces     # one category
ansible-playbook release_verification.yml --tags BOND-001       # one test
ansible-playbook release_verification.yml -l pair_1             # pair tests only
ansible-playbook release_verification.yml -l trio_1             # trio tests only (r1→r2→r3)

# CI with JUnit XML
JUNIT_OUTPUT_DIR=./test-results ansible-playbook release_verification.yml
```

## Connection settings (group_vars/vyos_hosts/all.yml)

```yaml
ansible_user: vyos
ansible_ssh_pass: vyos
ansible_network_os: vyos.vyos.vyos
ansible_connection: ansible.netcommon.network_cli
ansible_command_timeout: 30
ansible_connect_timeout: 10
```
