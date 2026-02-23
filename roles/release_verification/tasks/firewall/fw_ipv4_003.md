# FW-IPV4-003: IPv4 output filter and prerouting raw

Topology: 2-node symmetric
Runs on: r1, r2 — each router executes independently with its own variable values

## Steps

### Configure

```
set interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
set firewall ipv4 output filter rule 100 action 'drop'
set firewall ipv4 output filter rule 100 protocol 'icmp'
```

### Verify

```
ping {{ hostvars[rv_peer].rv_underlay_ip }} count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Configure

```
set firewall ipv4 output filter rule 50 action 'accept'
set firewall ipv4 output filter rule 50 protocol 'icmp'
```

### Assert

- ping {{ hostvars[rv_peer].rv_underlay_ip }} → 0% packet loss

### Configure

```
set firewall ipv4 prerouting raw rule 200 action 'drop'
set firewall ipv4 prerouting raw rule 200 protocol 'icmp'
set firewall ipv4 prerouting raw rule 200 source address '{{ hostvars[rv_peer].rv_underlay_ip }}'
```

### Verify

```
ping {{ hostvars[rv_peer].rv_underlay_ip }} count 3 deadline 5
```

### Assert

- '100% packet loss' in output

### Verify

```
show configuration commands | grep 'firewall ipv4'
```

### Assert

- 'output filter' in output
- 'prerouting raw' in output

## Cleanup

```
delete firewall ipv4 output filter rule 50
delete firewall ipv4 output filter rule 100
delete firewall ipv4 prerouting raw rule 200
delete interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
```
