# vyos-ansible-smoketests
Ansible deployment for VyOS smoketests

ansible-playbook main.yml

ansible-playbook main.yml -l r1 -e 'ansible_ssh_host=192.0.2.21'

ansible-playbook main.yml -e 'target_host=r1'

ansible-playbook main.yml --tags show

## Release verification (209 test cases, 31 implemented)

See `roles/release_verification/README.md` for full details, progress, and structure.

Tests are organized in `tasks/<category>/` subdirectories with shared helpers and a
test registry covering all 207 cases from `vyos-release-verification-test-cases.csv`.

```bash
ansible-playbook release_verification.yml                       # all
ansible-playbook release_verification.yml --tags interfaces     # one category
ansible-playbook release_verification.yml --tags BOND-001       # one test
ansible-playbook release_verification.yml -l pair_1             # pair tests only

# CI with JUnit XML
JUNIT_OUTPUT_DIR=./test-results ansible-playbook release_verification.yml
```
