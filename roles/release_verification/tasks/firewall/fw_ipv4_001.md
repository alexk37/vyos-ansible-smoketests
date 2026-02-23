# FW-IPV4-001: IPv4 input filter rules — real traffic enforcement

Topology: 2-node symmetric
Runs on: r1, r2 — each router executes independently with its own variable values

## Steps

### Configure

```
set interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
set firewall ipv4 input filter rule 100 action 'drop'
set firewall ipv4 input filter rule 100 protocol 'icmp'
set firewall ipv4 input filter rule 100 source address '{{ hostvars[rv_peer].rv_underlay_ip }}'
```

### Verify

```
ping {{ hostvars[rv_peer].rv_underlay_ip }} count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Configure

```
set firewall ipv4 input filter rule 50 action 'accept'
set firewall ipv4 input filter rule 50 protocol 'icmp'
set firewall ipv4 input filter rule 50 source address '{{ hostvars[rv_peer].rv_underlay_ip }}'
```

### Verify

```
show configuration commands | grep 'firewall ipv4 input filter rule'
```

### Assert

- 'rule 50' in output
- 'rule 100' in output
- 'accept' in output
- 'drop' in output
- ping {{ hostvars[rv_peer].rv_underlay_ip }} → 0% packet loss

## Cleanup

```
delete firewall ipv4 input filter rule 50
delete firewall ipv4 input filter rule 100
delete interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
```
