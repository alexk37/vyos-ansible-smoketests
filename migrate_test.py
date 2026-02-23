#!/usr/bin/env python3
"""
Migration Tool: Unittest Smoketests to Ansible

This script analyzes unittest smoketest files and generates Ansible role
templates and tasks to help with migration.

Usage:
    python3 migrate_test.py test_vpp.py
    python3 migrate_test.py test_protocols_bgp.py --output-dir roles/bgp_test
"""

import ast
import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


class TestAnalyzer(ast.NodeVisitor):
    """Analyze unittest test files to extract configuration and validation patterns"""
    
    def __init__(self):
        self.config_commands = []
        self.validation_commands = []
        self.operational_commands = []
        self.assertions = []
        self.file_reads = []
        self.process_checks = []
        self.current_test = None
        
    def visit_FunctionDef(self, node):
        """Track test methods"""
        if node.name.startswith('test_'):
            self.current_test = node.name
            self.generic_visit(node)
            self.current_test = None
        else:
            self.generic_visit(node)
    
    def visit_Call(self, node):
        """Extract method calls"""
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            
            # Configuration commands
            if method_name == 'cli_set':
                args = self._extract_args(node.args)
                if args:
                    self.config_commands.append({
                        'test': self.current_test,
                        'method': 'cli_set',
                        'args': args,
                        'line': node.lineno
                    })
            
            elif method_name == 'cli_delete':
                args = self._extract_args(node.args)
                if args:
                    self.config_commands.append({
                        'test': self.current_test,
                        'method': 'cli_delete',
                        'args': args,
                        'line': node.lineno
                    })
            
            # Operational commands
            elif method_name == 'op_mode':
                args = self._extract_args(node.args)
                if args:
                    self.operational_commands.append({
                        'test': self.current_test,
                        'command': args,
                        'line': node.lineno
                    })
            
            elif method_name == 'getFRRconfig':
                args = self._extract_args(node.args)
                self.validation_commands.append({
                    'test': self.current_test,
                    'method': 'getFRRconfig',
                    'args': args,
                    'line': node.lineno
                })
            
            # Assertions
            elif method_name.startswith('assert'):
                self.assertions.append({
                    'test': self.current_test,
                    'method': method_name,
                    'line': node.lineno
                })
            
            # File operations
            elif method_name == 'read_file':
                args = self._extract_args(node.args)
                if args:
                    self.file_reads.append({
                        'test': self.current_test,
                        'file': args[0] if isinstance(args[0], str) else None,
                        'line': node.lineno
                    })
            
            # Process checks
            elif 'process' in method_name.lower() or 'running' in method_name.lower():
                self.process_checks.append({
                    'test': self.current_test,
                    'method': method_name,
                    'line': node.lineno
                })
        
        self.generic_visit(node)
    
    def _extract_args(self, args):
        """Extract arguments from function call"""
        result = []
        for arg in args:
            if isinstance(arg, ast.Constant):
                result.append(arg.value)
            elif isinstance(arg, ast.List) or isinstance(arg, ast.Tuple):
                result.append([self._extract_value(elem) for elem in arg.elts])
            elif hasattr(ast, 'Str') and isinstance(arg, ast.Str):  # Python < 3.8
                result.append(arg.s)
            else:
                result.append(None)
        return result
    
    def _extract_value(self, node):
        """Extract value from AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif hasattr(ast, 'Str') and isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Name):
            return node.id
        return None


class AnsibleGenerator:
    """Generate Ansible role structure from analyzed test"""
    
    def __init__(self, test_name: str, analyzer: TestAnalyzer):
        self.test_name = test_name
        self.analyzer = analyzer
        self.role_name = self._role_name_from_test(test_name)
    
    def _role_name_from_test(self, test_name: str) -> str:
        """Convert test filename to role name"""
        # test_vpp.py -> vpp_test
        # test_protocols_bgp.py -> bgp_test
        name = test_name.replace('test_', '').replace('.py', '')
        name = name.replace('_', '_').replace('protocols_', '')
        return f"{name}_test"
    
    def generate_role_structure(self, output_dir: Path):
        """Generate complete Ansible role structure"""
        role_dir = output_dir / self.role_name
        role_dir.mkdir(parents=True, exist_ok=True)
        
        # Create directory structure
        (role_dir / 'tasks').mkdir(exist_ok=True)
        (role_dir / 'templates').mkdir(exist_ok=True)
        (role_dir / 'vars').mkdir(exist_ok=True)
        (role_dir / 'defaults').mkdir(exist_ok=True)
        
        # Generate files
        self._generate_main_yml(role_dir / 'tasks' / 'main.yml')
        self._generate_setup_yml(role_dir / 'tasks' / 'setup.yml')
        self._generate_validation_yml(role_dir / 'tasks' / 'validation.yml')
        self._generate_config_template(role_dir / 'templates' / f'{self.role_name}_config.j2')
        self._generate_vars(role_dir / 'vars' / 'main.yml')
        self._generate_defaults(role_dir / 'defaults' / 'main.yml')
        self._generate_readme(role_dir / 'README.md')
        
        print(f"Generated Ansible role: {role_dir}")
        return role_dir
    
    def _generate_main_yml(self, path: Path):
        """Generate main.yml task file"""
        content = """---
# Main entry point for {{ role_name }} tests

- name: Include setup tasks
  include_tasks: setup.yml
  tags:
    - {{ role_tag }}
    - setup

- name: Include validation tasks
  include_tasks: validation.yml
  tags:
    - {{ role_tag }}
    - validation
"""
        content = content.replace('{{ role_name }}', self.role_name)
        content = content.replace('{{ role_tag }}', self.role_name.replace('_test', ''))
        path.write_text(content)
    
    def _generate_setup_yml(self, path: Path):
        """Generate setup.yml with configuration tasks"""
        lines = []
        lines.append("---")
        lines.append("")
        lines.append("- name: Configure {{ role_name }}")
        lines.append("  vyos.vyos.vyos_config:")
        lines.append(f"    src: {self.role_name}_config.j2")
        lines.append("  tags:")
        lines.append(f"    - {self.role_name.replace('_test', '')}")
        lines.append("    - config")
        lines.append("    - setup")
        
        path.write_text('\n'.join(lines))
    
    def _generate_validation_yml(self, path: Path):
        """Generate validation.yml with check tasks"""
        lines = []
        lines.append("---")
        lines.append("")
        
        # Add operational command checks
        for cmd in self.analyzer.operational_commands:
            command_str = ' '.join(cmd['command']) if isinstance(cmd['command'], list) else str(cmd['command'])
            lines.append(f"# Validation from {cmd['test']} (line {cmd['line']})")
            lines.append(f"- name: Check {command_str}")
            lines.append("  vyos.vyos.vyos_command:")
            lines.append(f"    commands:")
            lines.append(f"      - {command_str}")
            lines.append(f"  register: {self._sanitize_var_name(command_str)}_output")
            lines.append("  tags:")
            lines.append(f"    - {self.role_name.replace('_test', '')}")
            lines.append("    - validation")
            lines.append("")
        
        # Add file read checks
        for file_read in self.analyzer.file_reads:
            if file_read['file']:
                lines.append(f"# File check from {file_read['test']} (line {file_read['line']})")
                lines.append(f"- name: Read {file_read['file']}")
                lines.append("  vyos.vyos.vyos_command:")
                lines.append(f"    commands:")
                lines.append(f"      - cat {file_read['file']}")
                lines.append(f"  register: {self._sanitize_var_name(file_read['file'])}_content")
                lines.append("  tags:")
                lines.append(f"    - {self.role_name.replace('_test', '')}")
                lines.append("    - validation")
                lines.append("")
        
        # Add process checks
        for proc_check in self.analyzer.process_checks:
            lines.append(f"# Process check from {proc_check['test']} (line {proc_check['line']})")
            lines.append(f"- name: Check process status")
            lines.append("  vyos.vyos.vyos_command:")
            lines.append("    commands:")
            lines.append("      - ps aux | grep '[p]rocess_name'")
            lines.append("  register: process_status")
            lines.append("  tags:")
            lines.append(f"    - {self.role_name.replace('_test', '')}")
            lines.append("    - validation")
            lines.append("")
            lines.append("- name: Verify process is running")
            lines.append("  fail:")
            lines.append("    msg: \"Process is not running\"")
            lines.append("  when: process_status.rc != 0")
            lines.append("  tags:")
            lines.append(f"    - {self.role_name.replace('_test', '')}")
            lines.append("    - validation")
            lines.append("")
        
        path.write_text('\n'.join(lines))
    
    def _generate_config_template(self, path: Path):
        """Generate Jinja2 configuration template"""
        lines = []
        lines.append("{# Generated from unittest smoketest #}")
        lines.append("")
        
        for cmd in self.analyzer.config_commands:
            if cmd['method'] == 'cli_set':
                config_path = cmd['args'][0] if cmd['args'] else []
                if isinstance(config_path, list):
                    # Convert ['vpp', 'settings', 'interface', 'eth1', 'driver', 'dpdk']
                    # to: set vpp settings interface eth1 driver 'dpdk'
                    set_cmd = "set " + " ".join(str(p) for p in config_path)
                    if len(cmd['args']) > 1 and cmd['args'][1]:
                        set_cmd += f" '{cmd['args'][1]}'"
                    lines.append(set_cmd)
            elif cmd['method'] == 'cli_delete':
                config_path = cmd['args'][0] if cmd['args'] else []
                if isinstance(config_path, list):
                    delete_cmd = "delete " + " ".join(str(p) for p in config_path)
                    lines.append(delete_cmd)
        
        path.write_text('\n'.join(lines))
    
    def _generate_vars(self, path: Path):
        """Generate variables file"""
        content = """---
# Variables for {{ role_name }} tests
# Override in group_vars or host_vars as needed
"""
        content = content.replace('{{ role_name }}', self.role_name)
        path.write_text(content)
    
    def _generate_defaults(self, path: Path):
        """Generate defaults file"""
        content = """---
# Default variables for {{ role_name }} tests
"""
        content = content.replace('{{ role_name }}', self.role_name)
        path.write_text(content)
    
    def _generate_readme(self, path: Path):
        """Generate README for the role"""
        content = f"""# {self.role_name}

Ansible role migrated from unittest smoketest: {self.test_name}

## Usage

```bash
ansible-playbook main.yml --tags {self.role_name.replace('_test', '')}
```

## Variables

See `vars/main.yml` and `defaults/main.yml` for configurable variables.

## Tasks

- **setup.yml**: Configuration setup
- **validation.yml**: Validation checks

## Tags

- `{self.role_name.replace('_test', '')}`: All tasks for this role
- `config`: Configuration tasks
- `validation`: Validation tasks
"""
        path.write_text(content)
    
    def _sanitize_var_name(self, name: str) -> str:
        """Convert string to valid Ansible variable name"""
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name)
        return name.lower().strip('_')


def analyze_test_file(file_path: Path) -> TestAnalyzer:
    """Analyze a unittest test file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content)
    analyzer = TestAnalyzer()
    analyzer.visit(tree)
    
    return analyzer


def main():
    parser = argparse.ArgumentParser(description='Migrate unittest smoketests to Ansible')
    parser.add_argument('test_file', help='Path to unittest test file')
    parser.add_argument('--output-dir', default='roles', help='Output directory for Ansible roles')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not generate')
    
    args = parser.parse_args()
    
    test_file = Path(args.test_file)
    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        sys.exit(1)
    
    print(f"Analyzing: {test_file}")
    analyzer = analyze_test_file(test_file)
    
    print(f"\nFound:")
    print(f"  Configuration commands: {len(analyzer.config_commands)}")
    print(f"  Validation commands: {len(analyzer.validation_commands)}")
    print(f"  Operational commands: {len(analyzer.operational_commands)}")
    print(f"  Assertions: {len(analyzer.assertions)}")
    print(f"  File reads: {len(analyzer.file_reads)}")
    print(f"  Process checks: {len(analyzer.process_checks)}")
    
    if not args.analyze_only:
        output_dir = Path(args.output_dir)
        generator = AnsibleGenerator(test_file.name, analyzer)
        role_dir = generator.generate_role_structure(output_dir)
        print(f"\nMigration complete! Review and customize the generated role in: {role_dir}")


if __name__ == '__main__':
    main()

