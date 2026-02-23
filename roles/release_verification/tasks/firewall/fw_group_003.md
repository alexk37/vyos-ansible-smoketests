# FW-GROUP-003: Firewall IPv6 address-group and domain-group

Topology: 2-node symmetric
Runs on: r1, r2 — each router executes independently with its own variable values

## Configure commands

```
set interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
set interfaces ethernet eth1 address '{{ rv_ipv6_underlay_ip }}/64'
set firewall group ipv6-address-group rv_ipv6 address '{{ hostvars[rv_peer].rv_ipv6_underlay_ip }}'
set firewall group domain-group rv_domain address 'vyos.net'
set firewall ipv6 input filter rule 300 action 'accept'
set firewall ipv6 input filter rule 300 protocol 'ipv6-icmp'
set firewall ipv6 input filter rule 300 source group address-group 'rv_ipv6'
```

## Verification commands

```
show firewall group
show configuration commands | grep 'firewall group domain-group'
```

## Assertions

- 'rv_ipv6' in output
- hostvars[rv_peer].rv_ipv6_underlay_ip in output
- 'rv_domain' in output
- 'vyos.net' in output
- ping {{ hostvars[rv_peer].rv_ipv6_underlay_ip }} → 0% packet loss

## Cleanup

```
delete firewall ipv6 input filter rule 300
delete firewall group ipv6-address-group rv_ipv6
delete firewall group domain-group rv_domain
delete interfaces ethernet eth1 address '{{ rv_underlay_ip }}/24'
delete interfaces ethernet eth1 address '{{ rv_ipv6_underlay_ip }}/64'
```
