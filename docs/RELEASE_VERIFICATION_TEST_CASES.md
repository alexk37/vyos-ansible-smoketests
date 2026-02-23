# Release Verification Test Cases (first 25)

Inventory usage, configuration, and exact verification method for each case.

**Inventory groups:**
- **vyos_hosts** – all routers; 1-node tests run per host.
- **pair_1** – r1 + r2; 2-node tests use `rv_peer`, per-test overlay IPs, and ping/traffic exchange.

**IP addressing scheme (2-node):**

| Test | r1 overlay | r2 overlay | Prefix |
|------|-----------|-----------|--------|
| ETH-001 | 10.30.0.1/30 | 10.30.0.2/30 | eth1 secondary |
| ETH-002 | 10.100.0.1/24 | 10.100.0.2/24 | eth1.100 VLAN |
| TUN-001 | 198.51.100.1/24 | 198.51.100.2/24 | IPIP tunnel |
| GENEVE-001 | 198.51.110.1/24 | 198.51.110.2/24 | GENEVE |
| L2TPV3-001 | 198.51.111.1/24 | 198.51.111.2/24 | L2TPv3 |
| VTI-001 | 198.51.112.1/24 | 198.51.112.2/24 | VTI |
| VXLAN-001 | 198.51.120.1/24 | 198.51.120.2/24 | VXLAN |
| WG-001 | 10.10.10.1/24 | 10.10.10.2/24 | WireGuard |
| LOOP-001 | 192.0.2.201/32 | 192.0.2.202/32 | Loopback (OSPF) |
| DUMMY-001 | 203.0.113.11/32 | 203.0.113.14/32 | Dummy (OSPF) |

---

## Per-test verification

### 1. BOND-001 – bonding
- **Inventory**: 1-node (vyos_hosts)
- **Config**: `bond0` mode 802.3ad, address, member interfaces.
- **Verify**: `show interfaces bonding bond0` contains bond name and members.
- **Cleanup**: delete `interfaces bonding bond0`.

### 2. BRIDGE-001 – bridge
- **Inventory**: 1-node (vyos_hosts)
- **Config**: `br0` with address and member interface.
- **Verify**: `show interfaces bridge br0` contains bridge name.
- **Cleanup**: delete `interfaces bridge br0`.

### 3. BRIDGE-002 – bridge firewall
- **Inventory**: 1-node (vyos_hosts)
- **Config**: `br0` + bridge firewall `rv_br_fw` with accept ICMP rule, applied on bridge input.
- **Verify**: `show firewall bridge` contains `rv_br_fw`; `show interfaces bridge br0` contains `rv_br_fw`.
- **Cleanup**: delete firewall rule + bridge.

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
- **Inventory**: 1-node (vyos_hosts)
- **Config**: PPPoE client with source-interface and auth (commit may fail without server).
- **Verify**: `show interfaces pppoe` (config accepted or graceful failure).
- **Cleanup**: delete pppoe config if applied.

### 15. PETH-001 – pseudo-ethernet
- **Inventory**: 1-node (vyos_hosts)
- **Config**: pseudo-ethernet with source-interface bound to eth.
- **Verify**: `show interfaces pseudo-ethernet` contains source-interface.
- **Cleanup**: delete pseudo-ethernet.

### 16. SSTP-001 – SSTP client
- **Inventory**: 1-node (vyos_hosts)
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
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `vti0` address `198.51.112.1/24`; r2 mirror with `.2` (from `rv_vti_overlay_ip`).
- **Verify**: `show interfaces vti vti0` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_vti_overlay_ip`.
- **Cleanup**: delete `interfaces vti vti0`.

### 20. VXLAN-001 – VXLAN
- **Inventory**: **2-node (pair_1)**
- **Config**: r1 `vxlan0 vni 10`, remote=r2_underlay, address `198.51.120.1/24`; r2 mirror with `.2`.
- **Verify**: `show interfaces vxlan vxlan0` contains interface.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_vxlan_overlay_ip` over VXLAN.
- **Cleanup**: delete `interfaces vxlan vxlan0`.

### 21. WLAN-001 – wireless
- **Inventory**: 1-node (vyos_hosts)
- **Config**: `show interfaces wireless`; optionally configure wlan0 if hardware present.
- **Verify**: show command runs without error.
- **Cleanup**: delete wireless config if applied.

### 22. WWAN-001 – WWAN
- **Inventory**: 1-node (vyos_hosts)
- **Config**: none.
- **Verify**: `show interfaces wwan` runs without error (exit code 0).
- **Cleanup**: none.

### 23. FW-GLOBAL-001 – firewall global options
- **Inventory**: **2-node (pair_1)**
- **Config**: `firewall global-options all-ping enable`, `broadcast-ping enable`.
- **Verify**: `show firewall` contains `all-ping` and `broadcast-ping`.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_underlay_ip` (ICMP allowed by global options).
- **Cleanup**: delete global-options `all-ping` and `broadcast-ping`.

### 24. FW-GROUP-001 – address-group and network-group
- **Inventory**: **2-node (pair_1)**
- **Config**: address-group `rv_addr` with peer's underlay IP; network-group `rv_net` with peer's /24. Firewall input rule 100: accept ICMP from `rv_addr`.
- **Verify**: `show firewall group` contains `rv_addr` and `rv_net`.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_underlay_ip` (traffic matched by address-group rule).
- **Cleanup**: delete firewall rule 100 + groups.

### 25. FW-GROUP-002 – port-group and interface-group
- **Inventory**: **2-node (pair_1)**
- **Config**: port-group `rv_port` with ports 22, 80, 443; interface-group `rv_if` with `eth1`. Firewall input rule 200: accept TCP to `rv_port`.
- **Verify**: `show firewall group` contains `rv_port` and `rv_if`.
- **2-node verify**: each router pings `hostvars[rv_peer].rv_underlay_ip` (basic reachability; TCP port test optional).
- **Cleanup**: delete firewall rule 200 + groups.

---

## Summary

| Test | Inventory | Verification method |
|------|-----------|---------------------|
| BOND-001 | 1-node | show bonding + members |
| BRIDGE-001 | 1-node | show bridge |
| BRIDGE-002 | 1-node | show firewall bridge + bridge |
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
| VTI-001 | **pair_1** | show + **ping peer VTI overlay** |
| VXLAN-001 | **pair_1** | show + **ping peer VXLAN overlay** |
| WLAN-001 | 1-node | show wireless |
| WWAN-001 | 1-node | show wwan |
| FW-GLOBAL-001 | **pair_1** | show + **ping peer** (ICMP allowed) |
| FW-GROUP-001 | **pair_1** | show groups + **ping peer** (address-group rule) |
| FW-GROUP-002 | **pair_1** | show groups + **ping peer** (port-group rule) |

**2-node tests: 14 of 25** use pair_1 with explicit ping or traffic exchange between r1 and r2.
**1-node tests: 11 of 25** remain single-router (config + show) where pair adds little value or requires infrastructure not yet in place (certs, PPPoE server, MACsec keys, etc.).
