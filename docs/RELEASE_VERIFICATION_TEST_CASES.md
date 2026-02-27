# Release Verification Test Cases

Inventory usage, configuration, and exact verification method for each case.

**Inventory groups:**
- **vyos_hosts** – all routers; 1-node tests run per host.
- **pair_1** – r1 + r2; 2-node tests use `rv_peer`, per-test overlay IPs, and ping/traffic exchange.
- **trio_1** – r1 + r2 + r3; 3-node tests use all three routers with asymmetric roles.

**IP addressing scheme (2-node):**

| Test | r1 overlay | r2 overlay | Prefix |
|------|-----------|-----------|--------|
| ETH-001 | 10.30.0.1/30 | 10.30.0.2/30 | eth1 secondary |
| ETH-002 | 10.100.0.1/24 | 10.100.0.2/24 | eth1.100 VLAN |
| TUN-001 | 198.51.100.1/24 | 198.51.100.2/24 | IPIP tunnel |
| GENEVE-001 | 198.51.110.1/24 | 198.51.110.2/24 | GENEVE |
| L2TPV3-001 | 198.51.111.1/24 | 198.51.111.2/24 | L2TPv3 |
| VXLAN-001 | 198.51.120.1/24 | 198.51.120.2/24 | VXLAN |
| WG-001 | 10.10.10.1/24 | 10.10.10.2/24 | WireGuard |
| LOOP-001 | 192.0.2.201/32 | 192.0.2.202/32 | Loopback (OSPF) |
| DUMMY-001 | 203.0.113.11/32 | 203.0.113.14/32 | Dummy (OSPF) |

**IP addressing scheme (3-node):**

| Test | r1 role | r2 role | r3 role |
|------|---------|---------|---------|
| FW-IPV4-002 | source (10.0.2.1) | forward router (10.0.2.2 + 10.0.3.2) | destination (10.0.3.3) |
| FW-IPV6-001 | source (fd00:0:2::1) | forward router (fd00:0:2::2 + fd00:0:3::2) | destination (fd00:0:3::3) |
| FW-BRIDGE-001 | left host (eth3 10.40.0.1) | bridge r2 (br0: eth3+eth2, 10.40.0.2) | right host (eth1 10.40.0.3) |

---

## Per-test verification

### 1. BOND-001 – bonding
- **Inventory**: 1-node (r1)
- **Config**: `bond0` mode 802.3ad, address, member interfaces eth1+eth2.
- **Verify**: `show interfaces bonding bond0 detail` contains bond name and both members.
- **Cleanup**: delete `interfaces bonding bond0`.

### 2. BRIDGE-001 – bridge
- **Inventory**: 1-node (vyos_hosts)
- **Config**: `br0` with address and member interface.
- **Verify**: `show interfaces bridge br0` contains bridge name.
- **Cleanup**: delete `interfaces bridge br0`.

### 3. BRIDGE-002 – VLAN-aware bridge and connectivity
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 and r2 each create VLAN-aware `br0` with eth1 as member (`enable-vlan`, `native-vlan 10`, `allowed-vlan 10`); IP on `br0 vif 10` (from `rv_bridge_vlan_ip`: 10.50.0.1/24, 10.50.0.2/24).
- **Verify**: `show bridge vlan` contains VLAN 10 and bridge/member interface (confirms VLAN filtering active).
- **2-node verify**: each router pings `hostvars[rv_peer].rv_bridge_vlan_ip` over the VLAN-aware bridge.
- **Cleanup**: delete `interfaces bridge br0`.

### 4. DUMMY-001 – dummy
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `dum0 = 203.0.113.11/32`, r2 `dum0 = 203.0.113.14/32` (from `rv_dummy_ip`).
- **Verify**: `show interfaces dummy dum0` contains address.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_dummy_ip` (reachable via OSPF).
- **Cleanup**: delete `interfaces dummy dum0`.

### 5. ETH-001 – ethernet address
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `eth1 += 10.30.0.1/30`, r2 `eth1 += 10.30.0.2/30` (from `rv_eth_test_ip`).
- **Verify**: `show interfaces ethernet eth1` contains test IP.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_eth_test_ip` (direct link).
- **Cleanup**: delete the test address from eth1.

### 6. ETH-002 – VLAN subinterface
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `eth1.100 = 10.100.0.1/24`, r2 `eth1.100 = 10.100.0.2/24` (from `rv_vlan_test_ip`).
- **Verify**: `show interfaces ethernet eth1 vif 100` contains VLAN 100.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_vlan_test_ip` across VLAN 100.
- **Cleanup**: delete `eth1 vif 100`.

### 7. GENEVE-001 – GENEVE tunnel
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `geneve0 vni 10, remote=r2_underlay, address 198.51.110.1/24`; r2 mirror with `.2`.
- **Verify**: `show interfaces geneve geneve0` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_geneve_overlay_ip` over GENEVE.
- **Cleanup**: delete `interfaces geneve geneve0`.

### 8. L2TPV3-001 – L2TPv3 pseudowire
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `l2tpeth100` source=r1_underlay, remote=r2_underlay, tunnel/session IDs=100, address `198.51.111.1/24`; r2 mirror with `.2`.
- **Verify**: `show interfaces l2tpv3 l2tpeth100` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_l2tpv3_overlay_ip` over the pseudowire.
- **Cleanup**: delete `interfaces l2tpv3 l2tpeth100`.

### 9. LOOP-001 – loopback
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `lo = 192.0.2.201/32`, r2 `lo = 192.0.2.202/32` (from `rv_loop_test_ip`); OSPF `redistribute connected`.
- **Verify**: `show interfaces loopback lo` contains test IP.
- **2-node verify**: 5s pause for OSPF convergence, then each router pings `hostvars[rv_peer].rv_loop_test_ip`.
- **Cleanup**: delete loopback test address + `redistribute connected`.

### 10. MACSEC-001 – MACsec
- **Inventory**: 1-node (vyos_hosts)
- **Config**: MACsec config on eth interface (key placeholder; commit may fail without valid keys).
- **Verify**: `show interfaces ethernet` (config accepted or graceful failure).
- **Cleanup**: delete macsec config if applied.

### 11. OVPN-001 – OpenVPN
- **Inventory**: 1-node (vyos_hosts)
- **Config**: OpenVPN server mode, subnet, TLS paths (commit may fail without certs).
- **Verify**: `show interfaces openvpn` (config accepted or graceful failure).
- **Cleanup**: delete openvpn config if applied.

### 12. WG-001 – WireGuard
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `wg0` with `rv_wg_privkey`, overlay `10.10.10.1/24`, peer=r2 (r2's pubkey, allowed-ips, endpoint); r2 mirror with `.2` and r1's pubkey.
- **Verify**: `show interfaces wireguard wg0` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_wg_overlay_ip` over WireGuard.
- **Cleanup**: delete `interfaces wireguard wg0`.

### 13. WG-002 – WG key generation
- **Inventory**: 1-node (vyos_hosts)
- **Config**: none (op-mode only).
- **Verify**: `wg genkey` produces ≥40 chars; `wg genpsk` produces ≥40 chars.
- **Cleanup**: none.

### 14. PPPOE-001 – PPPoE client
- **Inventory**: 1-node (r1)
- **Config**: PPPoE client with source-interface and auth (commit may fail without server).
- **Verify**: `show interfaces pppoe` (config accepted or graceful failure).
- **Cleanup**: delete pppoe config if applied.

### 15. PETH-001 – pseudo-ethernet
- **Inventory**: 1-node (vyos_hosts)
- **Config**: pseudo-ethernet with source-interface bound to eth.
- **Verify**: `show interfaces pseudo-ethernet` contains source-interface.
- **Cleanup**: delete pseudo-ethernet.

### 16. SSTP-001 – SSTP client
- **Inventory**: 1-node (r1)
- **Config**: SSTP client with server and auth (commit may fail).
- **Verify**: `show interfaces sstp-client` (config accepted or graceful failure).
- **Cleanup**: delete sstp-client if applied.

### 17. TUN-001 – IPIP tunnel
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `tun0` IPIP local=r1_underlay, remote=r2_underlay, address `198.51.100.1/24`; r2 mirror with `.2`.
- **Verify**: `show interfaces tunnel tun0` contains `tun0` and `ipip`.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_tunnel_overlay_ip` over IPIP tunnel.
- **Cleanup**: delete `interfaces tunnel tun0`.

### 18. VETH-001 – virtual-ethernet
- **Inventory**: 1-node (vyos_hosts)
- **Config**: veth0/veth1 pair with peer-name, address on veth0.
- **Verify**: `show interfaces virtual-ethernet veth0` contains `veth0`.
- **Cleanup**: delete both veth0 and veth1.

### 19. VTI-001 – VTI (IPsec)
- **Inventory**: 1-node (r1)
- **Config**: `vti0` with address (from `rv_vti_overlay_ip`).
- **Verify**: `show interfaces vti vti0` contains interface name.
- **Note**: config-only — VTI requires a live IPsec SA to forward traffic; no ping test.
- **Cleanup**: delete `interfaces vti vti0`.

### 20. VXLAN-001 – VXLAN
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `vxlan0 vni 10`, remote=r2_underlay, address `198.51.120.1/24`; r2 mirror with `.2`.
- **Verify**: `show interfaces vxlan vxlan0` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_vxlan_overlay_ip` over VXLAN.
- **Cleanup**: delete `interfaces vxlan vxlan0`.

### 21. WLAN-001 – wireless
- **Inventory**: 1-node (vyos_hosts)
- **Config**: optionally configure wlan0 if hardware present.
- **Verify**: `show interfaces wireless` runs without error.
- **Cleanup**: delete wireless config if applied.

### 22. WWAN-001 – WWAN
- **Inventory**: 1-node (vyos_hosts)
- **Config**: none.
- **Verify**: `show interfaces wwan` runs without error (exit code 0).
- **Cleanup**: delete wwan config if applied.

### 23. FW-GLOBAL-001 – firewall global options
- **Inventory**: **2-node (pair_1)**
- **Config**: `firewall global-options all-ping enable`, `broadcast-ping enable`.
- **Verify**: `show firewall` contains `all-ping` and `broadcast-ping`.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_underlay_ip` (ICMP allowed by global options).
- **Cleanup**: delete global-options `all-ping` and `broadcast-ping`.

### 24. FW-GROUP-001 – address-group and network-group
- **Inventory**: **2-node (pair_1)**
- **Config**: address-group `rv_addr` with peer's underlay IP; network-group `rv_net` with peer's /24. Firewall `ipv4 input filter`: `default-action drop`, rule 1 accept established/related (keeps management SSH alive), rule 100 accept ICMP from `rv_addr`.
- **Verify**: `show firewall group` contains groups and member IPs.
- **2-node verify**: each router pings peer — passes only because the address-group rule explicitly accepts it (default-action is drop, so the rule is what allows traffic).
- **Cleanup**: delete firewall rule 100 + default-action + groups.

### 25. FW-GROUP-002 – port-group and interface-group
- **Inventory**: **2-node (pair_1)**
- **Config**: port-group `rv_port` with ports 22, 80, 443; interface-group `rv_if` with `eth1`. Firewall `ipv4 input filter`: `default-action drop`, rule 200 accept TCP to `rv_port`.
- **Verify (baseline)**: ping peer before applying firewall — 0% loss (proves eth1 works).
- **Verify (groups)**: `show firewall group` contains `rv_port` and `rv_if` with correct members; `show firewall ipv4 input filter` contains `drop` and port-group reference.
- **Verify (enforcement)**: ping peer after firewall — 100% loss (ICMP not in port-group, blocked by default-action drop). SSH connection stays alive throughout (proves TCP/22 is accepted by rule 200).
- **Cleanup**: delete firewall rule 200 + default-action + groups.

### 26. FW-GROUP-003 – IPv6 address-group and domain-group
- **Inventory**: **2-node (pair_1)**
- **Config**: IPv6 underlay on eth1 (from `rv_ipv6_underlay_ip`); ipv6-address-group `rv_ipv6_addr` with peer's IPv6 address; domain-group `rv_domain` with `vyos.net`. Firewall `ipv6 input filter`: `default-action drop`, rule 1 accept established/related, rule 300 accept IPv6-ICMP from `rv_ipv6_addr`.
- **Verify**: `show firewall group` contains IPv6 address-group with peer's address and domain-group with `vyos.net`; `show configuration commands` confirms domain-group config.
- **2-node verify**: each router pings peer over IPv6 — passes only because the ipv6-address-group rule explicitly accepts it.
- **Cleanup**: delete firewall rule 300 + default-action + groups.

### 27. FW-IPV4-001 – IPv4 input filter rule ordering
- **Inventory**: **2-node (pair_1)**
- **Config**: eth1 underlay IPs. Firewall `ipv4 input filter`:
  - Phase 1: rule 100 drop ICMP from peer.
  - Phase 2: add rule 50 accept ICMP from peer (lower number = higher priority).
- **Verify (phase 1)**: ping peer → 100% packet loss (drop rule blocks ICMP).
- **Verify (phase 2)**: ping peer → 0% packet loss (accept rule 50 overrides drop rule 100).
- **Cleanup**: delete firewall rules + eth1 IPs.

### 28. FW-IPV4-002 – IPv4 forward filter (3-node)
- **Inventory**: **3-node (trio_1)**
- **Topology**: r1 (source) → r2 (forward router with filter) → r3 (destination). Static routes on r1/r3; forward filter applied on r2.
- **Config**: r1 `eth1=10.0.2.1/24`, r2 `eth1=10.0.2.2/24 + eth2=10.0.3.2/24`, r3 `eth1=10.0.3.3/24`; static routes r1→r3 and r3→r1 via r2.
- **Verify (baseline)**: ping r1→r3 succeeds (routing works before any filter).
- **Verify (phase 1)**: add drop rule 100 on r2 forward chain → r1→r3 ICMP blocked (100% loss).
- **Verify (phase 2)**: add accept rule 50 on r2 → r1→r3 ICMP forwarded again (rule 50 beats rule 100).
- **Cleanup**: delete forward filter rules + static routes.

### 29. FW-IPV4-003 – IPv4 output filter and prerouting raw
- **Inventory**: **2-node (pair_1)**
- **Config**: eth1 underlay IPs. Two phases testing distinct nftables hooks:
  - Phase A: `ipv4 output filter` rule 100 drop ICMP; then rule 50 accept.
  - Phase B: `ipv4 prerouting raw` rule 200 drop ICMP from peer.
- **Verify (phase A drop)**: ping peer → 100% loss (router's own ICMP blocked at output chain).
- **Verify (phase A accept)**: ping peer → 0% loss (rule 50 overrides rule 100).
- **Verify (phase B)**: ping peer → 100% loss (peer's ICMP blocked at prerouting raw before conntrack).
- **Cleanup**: delete output filter rules + prerouting raw rules + eth1 IPs.

### 30. FW-IPV6-001 – IPv6 input, forward, and output filter (3-node)
- **Inventory**: **3-node (trio_1)**
- **Topology**: r1 (source) → r2 (middle router with input/forward/output filters) → r3 (destination). IPv6 static routes on r1/r3.
- **Config**: r1 `eth1=fd00:0:2::1/64`, r2 `eth1=fd00:0:2::2/64 + eth2=fd00:0:3::2/64`, r3 `eth1=fd00:0:3::3/64`.
- **Verify (input)**: drop/accept rule ordering on IPv6-ICMP destined to r2 itself (r1→r2).
- **Verify (output)**: drop/accept rule ordering on IPv6-ICMP originated by r2 (r2→r1).
- **Verify (forward)**: drop/accept rule ordering on forwarded r1→r3 IPv6-ICMP traffic.
- **Cleanup**: delete all IPv6 firewall rules + static routes.

### 31. FW-BRIDGE-001 – bridge firewall forward/input/output/prerouting (3-node)
- **Inventory**: **3-node (trio_1)**
- **Topology**: r1 (left host, eth3=10.40.0.1) ↔ r2 bridge (br0 with eth3+eth2 members, br0=10.40.0.2) ↔ r3 (right host, eth1=10.40.0.3). r1-eth3 directly cabled to r2-eth3; r3-eth1 on shared switch via r2-eth2.
- **Config**: r2 creates `br0` with eth3+eth2 as members; r1/r3 get addresses on their respective interfaces.
- **Verify (forward)**: r1→r3 ICMP crosses bridge; drop rule blocks it; accept rule 50 overrides.
- **Verify (input)**: r1→br0 IP ICMP; drop rule blocks it; accept rule 50 overrides.
- **Verify (output)**: r2→r1 ICMP from br0; drop rule blocks it; accept rule 50 overrides.
- **Verify (prerouting)**: config commit of prerouting ARP accept rule on r2 (config-only).
- **Cleanup**: delete all bridge firewall rules + bridge + interface addresses.

---

## Summary

| Test | Inventory | Verification method |
|------|-----------|---------------------|
| BOND-001 | 1-node | show bonding + members |
| BRIDGE-001 | 1-node | show bridge |
| BRIDGE-002 | **pair_1** | show VLAN-aware bridge + **ping peer** (br0 vif 10) |
| DUMMY-001 | **pair_1** | show + **ping peer dummy** (OSPF) |
| ETH-001 | **pair_1** | show + **ping peer test IP** (direct) |
| ETH-002 | **pair_1** | show + **ping peer VLAN IP** (eth1.100) |
| GENEVE-001 | **pair_1** | show + **ping peer GENEVE overlay** |
| L2TPV3-001 | **pair_1** | show + **ping peer L2TPv3 overlay** |
| LOOP-001 | **pair_1** | show + **ping peer loopback** (OSPF) |
| MACSEC-001 | 1-node | show (config-only; keys needed) |
| OVPN-001 | 1-node | show (config-only; certs needed) |
| WG-001 | **pair_1** | show + **ping peer WG overlay** |
| WG-002 | 1-node | wg genkey / genpsk output |
| PPPOE-001 | 1-node | show (config-only; server needed) |
| PETH-001 | 1-node | show pseudo-ethernet |
| SSTP-001 | 1-node | show (config-only; server needed) |
| TUN-001 | **pair_1** | show + **ping peer IPIP overlay** |
| VETH-001 | 1-node | show virtual-ethernet |
| VTI-001 | 1-node | show vti (config-only; IPsec SA needed) |
| VXLAN-001 | **pair_1** | show + **ping peer VXLAN overlay** |
| WLAN-001 | 1-node | show wireless |
| WWAN-001 | 1-node | show wwan |
| FW-GLOBAL-001 | **pair_1** | show + **ping peer** (ICMP allowed by global options) |
| FW-GROUP-001 | **pair_1** | show groups + **ping peer** (address-group rule explicitly allows; default-action drop) |
| FW-GROUP-002 | **pair_1** | show groups + baseline ping 0% + **post-firewall ping 100% loss** (ICMP blocked; TCP/22 alive proves port-group rule) |
| FW-GROUP-003 | **pair_1** | show groups + **IPv6 ping peer** (ipv6-address-group rule explicitly allows; default-action drop) |
| FW-IPV4-001 | **pair_1** | drop rule → **100% loss**; add accept rule → **0% loss** (input filter rule ordering) |
| FW-IPV4-002 | **trio_1** | baseline ping r1→r3, then drop/accept rule ordering on r2 forward chain |
| FW-IPV4-003 | **pair_1** | output filter drop/accept + prerouting raw drop (two distinct nftables hooks) |
| FW-IPV6-001 | **trio_1** | IPv6 drop/accept rule ordering on r2 input + output + forward chains |
| FW-BRIDGE-001 | **trio_1** | bridge FORWARD/INPUT/OUTPUT/PREROUTING hooks with real ICMP block/allow |

**1-node tests: 12** — single-router config + show (VTI-001 and PPPOE-001 also run on r1 only).
**2-node tests: 16** — pair_1; ping or traffic enforcement between r1 and r2.
**3-node tests: 3** — trio_1; asymmetric roles (source / middle router or bridge / destination).
