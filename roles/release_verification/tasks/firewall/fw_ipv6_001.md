# FW-IPV6-001: IPv6 input, forward, and output filter rules

Topology: 3-node asymmetric
- r1: source — eth1 fd00:0:2::1/64, static route fd00:0:3::/64 → fd00:0:2::2
- r2: middle router — eth1 fd00:0:2::2/64, eth2 fd00:0:3::2/64; applies all filters
- r3: destination — eth1 fd00:0:3::3/64, static route fd00:0:2::/64 → fd00:0:3::2

Traffic paths:
- Phase A (input filter):   r1 → r2          (r2 INPUT chain)
- Phase B (output filter):  r1 → r2          (r1 OUTPUT chain)
- Phase C (forward filter): r1 → r2 → r3     (r2 FORWARD chain)

NDP safety: Source/dest address matches target ULA (fd00:0:2::x). NDP uses fe80:: source
and ff02:: destinations which never match fd00:: rules.

## Phase 1: Underlay setup

### Configure (r1)

```
set interfaces ethernet eth1 address 'fd00:0:2::1/64'
set protocols static route6 fd00:0:3::/64 next-hop 'fd00:0:2::2'
```

### Configure (r2)

```
set interfaces ethernet eth1 address 'fd00:0:2::2/64'
set interfaces ethernet eth2 address 'fd00:0:3::2/64'
```

### Configure (r3)

```
set interfaces ethernet eth1 address 'fd00:0:3::3/64'
set protocols static route6 fd00:0:2::/64 next-hop 'fd00:0:3::2'
```

## Phase 3: Baseline

### Verify (r1)

```
ping fd00:0:3::3 count 3 deadline 10
```

### Assert

- ', 0% packet loss' in output

## Phase A: IPv6 input filter

### Configure (r2)

```
set firewall ipv6 input filter rule 100 action 'drop'
set firewall ipv6 input filter rule 100 protocol 'ipv6-icmp'
set firewall ipv6 input filter rule 100 source address 'fd00:0:2::1'
```

### Verify (r1)

```
ping fd00:0:2::2 count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Configure (r2)

```
set firewall ipv6 input filter rule 50 action 'accept'
set firewall ipv6 input filter rule 50 protocol 'ipv6-icmp'
set firewall ipv6 input filter rule 50 source address 'fd00:0:2::1'
```

### Assert

- ping fd00:0:2::2 from r1 → ', 0% packet loss' (rule 50 accept wins over rule 100 drop)

## Phase B: IPv6 output filter

### Configure (r1)

```
set firewall ipv6 output filter rule 100 action 'drop'
set firewall ipv6 output filter rule 100 protocol 'ipv6-icmp'
set firewall ipv6 output filter rule 100 destination address 'fd00:0:2::2'
```

### Verify (r1)

```
ping fd00:0:2::2 count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Configure (r1)

```
set firewall ipv6 output filter rule 50 action 'accept'
set firewall ipv6 output filter rule 50 protocol 'ipv6-icmp'
set firewall ipv6 output filter rule 50 destination address 'fd00:0:2::2'
```

### Assert

- ping fd00:0:2::2 from r1 → ', 0% packet loss'

## Phase C: IPv6 forward filter

### Configure (r2)

```
set firewall ipv6 forward filter rule 100 action 'drop'
set firewall ipv6 forward filter rule 100 protocol 'ipv6-icmp'
set firewall ipv6 forward filter rule 100 source address 'fd00:0:2::1'
```

### Verify (r1)

```
ping fd00:0:3::3 count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Configure (r2)

```
set firewall ipv6 forward filter rule 50 action 'accept'
set firewall ipv6 forward filter rule 50 protocol 'ipv6-icmp'
set firewall ipv6 forward filter rule 50 source address 'fd00:0:2::1'
```

### Assert

- ping fd00:0:3::3 from r1 → ', 0% packet loss' (rule 50 accept wins over rule 100 drop)

## Cleanup

```
# r2
delete firewall ipv6 input filter rule 50
delete firewall ipv6 input filter rule 100
delete firewall ipv6 forward filter rule 50
delete firewall ipv6 forward filter rule 100
delete interfaces ethernet eth1 address 'fd00:0:2::2/64'
delete interfaces ethernet eth2 address 'fd00:0:3::2/64'

# r1
delete firewall ipv6 output filter rule 50
delete firewall ipv6 output filter rule 100
delete protocols static route6 fd00:0:3::/64 next-hop 'fd00:0:2::2'
delete interfaces ethernet eth1 address 'fd00:0:2::1/64'

# r3
delete protocols static route6 fd00:0:2::/64 next-hop 'fd00:0:3::2'
delete interfaces ethernet eth1 address 'fd00:0:3::3/64'
```
