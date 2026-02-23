# Unittest to Ansible Mapping Reference

Quick reference guide for converting unittest smoketest patterns to Ansible.

## Method Mappings

### Configuration Methods

| Unittest | Ansible Equivalent |
|----------|-------------------|
| `self.cli_set(['path', 'to', 'config'], 'value')` | `vyos.vyos.vyos_config` with template or `lines` |
| `self.cli_delete(['path', 'to', 'config'])` | `vyos.vyos.vyos_config` with `lines: ["delete path to config"]` |
| `self.cli_commit()` | Automatic with `vyos_config` module |
| `self.cli_discard()` | Not needed (Ansible handles rollback) |
| `self.cli_save(file)` | `vyos.vyos.vyos_config` with `save: true` |

### Operational Commands

| Unittest | Ansible Equivalent |
|----------|-------------------|
| `self.op_mode(['show', 'version'])` | `vyos.vyos.vyos_command` with `commands: ["show version"]` |
| `self.getFRRconfig('router bgp')` | `vyos.vyos.vyos_command` with `commands: ["vtysh -c 'show running-config no-header'"]` |
| `self.getFRRopmode('show ip bgp', json=True)` | `vyos.vyos.vyos_command` with `commands: ["vtysh -c 'show ip bgp json'"]` |

### Assertions

| Unittest | Ansible Equivalent |
|----------|-------------------|
| `self.assertIn('text', string)` | `fail` module with `when: "'text' not in variable.stdout \| join('\n')"` |
| `self.assertTrue(condition)` | `fail` module with `when: "not condition"` |
| `self.assertEqual(a, b)` | `fail` module with `when: "a != b"` |
| `self.assertRaises(ConfigSessionError)` | `failed_when: false` + `fail` when `rc == 0` |

### File Operations

| Unittest | Ansible Equivalent |
|----------|-------------------|
| `read_file('/path/to/file')` | `vyos.vyos.vyos_command` with `commands: ["cat /path/to/file"]` |
| `os.path.exists('/path/to/file')` | `vyos.vyos.vyos_command` with `commands: ["test -f /path/to/file"]` |

### Process Operations

| Unittest | Ansible Equivalent |
|----------|-------------------|
| `process_named_running('process_name')` | `vyos.vyos.vyos_command` with `commands: ["ps aux \| grep '[p]rocess_name'"]` |

## Code Examples

### Example 1: Basic Configuration

**Unittest:**
```python
def test_basic(self):
    self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '192.168.1.1/24'])
    self.cli_commit()
```

**Ansible:**
```yaml
- name: Configure interface
  vyos.vyos.vyos_config:
    lines:
      - set interfaces ethernet eth0 address '192.168.1.1/24'
  tags:
    - interfaces
    - config
```

### Example 2: Configuration with Validation

**Unittest:**
```python
def test_with_validation(self):
    self.cli_set(['protocols', 'bgp', 'system-as', '64512'])
    self.cli_commit()
    frrconfig = self.getFRRconfig('router bgp')
    self.assertIn('router bgp 64512', frrconfig)
```

**Ansible:**
```yaml
- name: Configure BGP
  vyos.vyos.vyos_config:
    lines:
      - set protocols bgp system-as '64512'
  tags:
    - bgp
    - config

- name: Get FRR config
  vyos.vyos.vyos_command:
    commands:
      - vtysh -c "show running-config no-header"
  register: frr_config
  tags:
    - bgp
    - validation

- name: Verify BGP in FRR config
  fail:
    msg: "BGP not found in FRR configuration"
  when: "'router bgp 64512' not in frr_config.stdout | join('\n')"
  tags:
    - bgp
    - validation
```

### Example 3: Error Handling

**Unittest:**
```python
def test_error_handling(self):
    self.cli_set(['invalid', 'config'])
    with self.assertRaises(ConfigSessionError):
        self.cli_commit()
```

**Ansible:**
```yaml
- name: Attempt invalid configuration
  vyos.vyos.vyos_config:
    lines:
      - set invalid config
  register: config_result
  failed_when: false
  tags:
    - negative_test

- name: Verify configuration was rejected
  fail:
    msg: "Invalid configuration was accepted (should have failed)"
  when: config_result.rc == 0
  tags:
    - negative_test
```

### Example 4: File Content Check

**Unittest:**
```python
def test_file_content(self):
    config = read_file('/run/vpp/vpp.conf')
    self.assertIn('main-core 0', config)
```

**Ansible:**
```yaml
- name: Read VPP config file
  vyos.vyos.vyos_command:
    commands:
      - cat /run/vpp/vpp.conf
  register: vpp_config
  tags:
    - vpp
    - validation

- name: Verify config file content
  fail:
    msg: "Config file missing expected content"
  when: "'main-core 0' not in vpp_config.stdout | join('\n')"
  tags:
    - vpp
    - validation
```

### Example 5: Process Check

**Unittest:**
```python
def test_process(self):
    self.assertTrue(process_named_running('vpp_main'))
```

**Ansible:**
```yaml
- name: Check VPP process
  vyos.vyos.vyos_command:
    commands:
      - ps aux | grep '[v]pp_main'
  register: vpp_process
  tags:
    - vpp
    - validation

- name: Verify VPP is running
  fail:
    msg: "VPP process is not running"
  when: vpp_process.rc != 0
  tags:
    - vpp
    - validation
```

### Example 6: Multiple Commands

**Unittest:**
```python
def test_multiple_commands(self):
    out1 = self.op_mode(['show', 'version'])
    out2 = self.op_mode(['show', 'interfaces'])
    self.assertIn('VyOS', out1)
    self.assertIn('eth0', out2)
```

**Ansible:**
```yaml
- name: Run multiple show commands
  vyos.vyos.vyos_command:
    commands:
      - show version
      - show interfaces
  register: show_output
  tags:
    - validation

- name: Verify version output
  fail:
    msg: "Version check failed"
  when: "'VyOS' not in show_output.stdout[0]"
  tags:
    - validation

- name: Verify interfaces output
  fail:
    msg: "Interfaces check failed"
  when: "'eth0' not in show_output.stdout[1]"
  tags:
    - validation
```

## Template Patterns

### Simple Configuration Template

```jinja2
{# roles/feature_test/templates/feature_config.j2 #}
set interfaces ethernet {{ interface }} address '{{ address }}'
set protocols bgp system-as '{{ bgp_as }}'
```

### Conditional Configuration Template

```jinja2
{# roles/feature_test/templates/feature_config.j2 #}
set interfaces ethernet {{ interface }} address '{{ address }}'
{% if vpp_enabled %}
set vpp settings interface {{ interface }} driver '{{ vpp_driver }}'
{% endif %}
```

### Loop Configuration Template

```jinja2
{# roles/feature_test/templates/feature_config.j2 #}
{% for neighbor in bgp_neighbors %}
set protocols bgp neighbor {{ neighbor.address }} remote-as '{{ neighbor.as }}'
{% endfor %}
```

## Common Patterns

### Pattern: Setup → Configure → Validate → Cleanup

**Unittest:**
```python
def setUp(self):
    self.cli_set(['base', 'config'])

def test_feature(self):
    self.cli_set(['feature', 'config'])
    self.cli_commit()
    # validate

def tearDown(self):
    self.cli_delete(['feature'])
    self.cli_commit()
```

**Ansible:**
```yaml
# tasks/setup.yml
- name: Base configuration
  vyos.vyos.vyos_config:
    lines:
      - set base config
  tags:
    - setup

# tasks/main.yml
- name: Configure feature
  vyos.vyos.vyos_config:
    lines:
      - set feature config
  tags:
    - config

# tasks/validation.yml
- name: Validate feature
  vyos.vyos.vyos_command:
    commands:
      - show feature status
  register: feature_status
  tags:
    - validation

# tasks/cleanup.yml (optional)
- name: Cleanup feature
  vyos.vyos.vyos_config:
    lines:
      - delete feature
  when: cleanup | default(false)
  tags:
    - cleanup
```

## Tips

1. **Use Templates:** For complex configurations, use Jinja2 templates
2. **Register Outputs:** Always register command outputs for validation
3. **Tag Everything:** Use tags for flexible test execution
4. **Fail Explicitly:** Use `fail` module with clear error messages
5. **Test Incrementally:** Test each task independently

