# FW-IPV4-002: IPv4 forward filter rules — 3-node traffic enforcement

Topology: 3-node asymmetric
Runs on: r1, r2, r3 — 3-node asymmetric (each router runs different commands; see [r1]/[r2]/[r3] labels)
Labels:   [r1] = r1 only;  [r2] = r2 only;  [r3] = r3 only

## Steps

### Configure

```
[r1] set interfaces ethernet eth1 address '10.0.2.1/24'
[r2] set interfaces ethernet eth1 address '10.0.2.2/24'
[r2] set interfaces ethernet eth2 address '10.0.3.2/24'
[r3] set interfaces ethernet eth1 address '10.0.3.3/24'
[r1] set protocols static route 10.0.3.0/24 next-hop '10.0.2.2'
[r3] set protocols static route 10.0.2.0/24 next-hop '10.0.3.2'
```

### Verify

```
[r1] ping 10.0.3.3 count 3 deadline 10
```

### Assert

- [r1] ', 0% packet loss' in output

### Configure

```
[r2] set firewall ipv4 forward filter rule 100 action 'drop'
[r2] set firewall ipv4 forward filter rule 100 protocol 'icmp'
[r2] set firewall ipv4 forward filter rule 100 source address '10.0.2.1'
```

### Verify

```
[r1] ping 10.0.3.3 count 3 deadline 5
```

### Assert

- [r1] '100% packet loss' in output

### Configure

```
[r2] set firewall ipv4 forward filter rule 50 action 'accept'
[r2] set firewall ipv4 forward filter rule 50 protocol 'icmp'
[r2] set firewall ipv4 forward filter rule 50 source address '10.0.2.1'
```

### Verify

```
[r1] ping 10.0.3.3 count 3 deadline 10
```

### Assert

- [r1] ', 0% packet loss' in output

## Cleanup

```
delete firewall ipv4 forward filter rule 50
delete firewall ipv4 forward filter rule 100
delete protocols static route 10.0.3.0/24 next-hop '10.0.2.2'
delete protocols static route 10.0.2.0/24 next-hop '10.0.3.2'
delete interfaces ethernet eth1 address '10.0.2.1/24'
delete interfaces ethernet eth1 address '10.0.2.2/24'
delete interfaces ethernet eth2 address '10.0.3.2/24'
delete interfaces ethernet eth1 address '10.0.3.3/24'
```
