from __future__ import annotations

DOCUMENTATION = """
    name: vyos_clean
    type: stdout
    short_description: Clean VyOS release verification output
    description:
        - Replaces verbose JSON output with human-readable VyOS test results.
        - Shows VyOS commands executed, device output, and assertion results.
        - Prints a separator with elapsed time and PASS/FAIL after each test.
        - Recap shows totals and host status only.
"""

import re
import time

from ansible import constants as C
from ansible.plugins.callback import CallbackBase

_VYOS_CONFIG  = frozenset(('vyos.vyos.vyos_config',  'vyos_config'))
_VYOS_COMMAND = frozenset(('vyos.vyos.vyos_command',  'vyos_command'))
_ASSERT       = frozenset(('ansible.builtin.assert',  'assert'))
_DEBUG        = frozenset(('ansible.builtin.debug',   'debug'))
_SET_FACT     = frozenset(('ansible.builtin.set_fact','set_fact'))

_ROLE_PREFIX = 'release_verification : '
_TEST_ID_RE  = re.compile(r'^[A-Z][A-Z0-9]*(-[A-Z][A-Z0-9]*)*-\d+$')
_SEP_WIDTH   = 72


def _fmt_time(seconds):
    if seconds < 60:
        return f'{seconds:.1f}s'
    m, s = divmod(int(seconds), 60)
    return f'{m}m {s}s'


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE    = 'stdout'
    CALLBACK_NAME    = 'vyos_clean'

    def __init__(self):
        super().__init__()
        self._test_order   = []
        self._test_start   = {}
        self._test_end     = {}
        self._test_elapsed = {}
        self._test_status  = {}
        self._current_test = None
        self._play_start   = None

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_test_id(self, task):
        for tag in (task.tags or []):
            if _TEST_ID_RE.match(tag):
                return tag
        # Fallback: parse from task name prefix (e.g. "TUN-001 - Wait for eth1...")
        # Needed when import_tasks tag propagation doesn't reach nested helpers.
        name = self._name(task)
        if ' - ' in name:
            prefix = name.split(' - ')[0]
            if _TEST_ID_RE.match(prefix):
                return prefix
        return None

    def _name(self, task):
        n = task.get_name().strip()
        if n.startswith(_ROLE_PREFIX):
            n = n[len(_ROLE_PREFIX):]
        return n

    def _header(self, task, host, suffix=''):
        h = f'{self._name(task)} [{host}]'
        return f'{h} {suffix}' if suffix else h

    def _is_cleanup(self, task):
        return 'cleanup' in (task.tags or [])

    def _finalise_test(self, test_id):
        if test_id and test_id not in self._test_elapsed:
            end = self._test_end.get(test_id, time.monotonic())
            self._test_elapsed[test_id] = end - self._test_start[test_id]

    def _print_test_footer(self, test_id):
        elapsed = self._test_elapsed.get(test_id, 0.0)
        status  = self._test_status.get(test_id, 'PASS')
        if status == 'FAIL':
            color = C.COLOR_ERROR
        else:
            color = C.COLOR_OK
        mid    = f'  {test_id}  {_fmt_time(elapsed)}  {status}  '
        dashes = '─' * max(4, _SEP_WIDTH - len(mid))
        self._display.display('')
        self._display.display(dashes + mid + '─' * 4, color=color)
        self._display.display('')

    # ── playbook lifecycle ────────────────────────────────────────────────────

    def v2_playbook_on_play_start(self, play):
        self._play_start = time.monotonic()
        name = play.get_name().strip()
        self._display.banner(f'PLAY [{name}]' if name else 'PLAY')

    def v2_playbook_on_task_start(self, task, is_conditional):
        test_id = self._get_test_id(task)
        if test_id != self._current_test:
            self._finalise_test(self._current_test)
            if self._current_test:
                self._print_test_footer(self._current_test)
            if test_id and test_id not in self._test_start:
                self._test_start[test_id]  = time.monotonic()
                self._test_status[test_id] = 'PASS'
                self._test_order.append(test_id)
            self._current_test = test_id

    # ── runner: OK ────────────────────────────────────────────────────────────

    def v2_runner_on_ok(self, result):
        host   = result._host.get_name()
        task   = result._task
        action = task.action
        res    = result._result

        test_id = self._get_test_id(task)
        if test_id:
            self._test_end[test_id] = time.monotonic()

        if action in _SET_FACT:
            return

        if task.no_log:
            self._display.display(self._header(task, host, 'ok'), color=C.COLOR_OK)
            return

        if self._is_cleanup(task):
            changed = res.get('changed', False)
            self._display.display(
                self._header(task, host, 'changed' if changed else 'ok'),
                color=C.COLOR_CHANGED if changed else C.COLOR_OK,
            )
            return

        if action in _VYOS_CONFIG:
            commands = res.get('commands', [])
            changed  = res.get('changed', False)
            color    = C.COLOR_CHANGED if changed else C.COLOR_OK
            self._display.display(self._header(task, host), color=color)
            if commands:
                for cmd in commands:
                    self._display.display(f'  {cmd}', color=color)
            else:
                self._display.display('  (no changes)', color=C.COLOR_OK)
            return

        if action in _VYOS_COMMAND:
            task_cmds = task.args.get('commands', [])
            stdout    = res.get('stdout', [])
            self._display.display(self._header(task, host), color=C.COLOR_OK)
            for i, out in enumerate(stdout):
                if i < len(task_cmds):
                    cmd = task_cmds[i]
                    if isinstance(cmd, dict):
                        cmd = cmd.get('command', str(cmd))
                    self._display.display(f'  > {cmd}', color=C.COLOR_OK)
                for line in out.splitlines():
                    self._display.display(f'  {line}')
            return

        if action in _ASSERT:
            self._display.display(self._header(task, host, 'PASS'), color=C.COLOR_OK)
            return

        if action in _DEBUG:
            msg = res.get('msg', '')
            self._display.display(self._header(task, host), color=C.COLOR_OK)
            if msg:
                for line in str(msg).splitlines():
                    self._display.display(f'  {line}')
            return

        changed = res.get('changed', False)
        self._display.display(
            self._header(task, host, 'changed' if changed else 'ok'),
            color=C.COLOR_CHANGED if changed else C.COLOR_OK,
        )

    # ── runner: FAILED ────────────────────────────────────────────────────────

    def v2_runner_on_failed(self, result, ignore_errors=False):
        host   = result._host.get_name()
        task   = result._task
        action = task.action
        res    = result._result

        test_id = self._get_test_id(task)
        if test_id:
            self._test_end[test_id] = time.monotonic()
            if not ignore_errors:
                self._test_status[test_id] = 'FAIL'

        if action in _ASSERT:
            msg = res.get('msg', 'assertion failed')
            self._display.display(self._header(task, host, 'FAIL'), color=C.COLOR_ERROR)
            self._display.display(f'  {msg}', color=C.COLOR_ERROR)
        else:
            self._display.display(self._header(task, host, 'FAILED'), color=C.COLOR_ERROR)
            for key in ('msg', 'stderr', 'module_stderr'):
                val = res.get(key, '')
                if val:
                    for line in str(val).splitlines():
                        self._display.display(f'  {line}', color=C.COLOR_ERROR)
            stdout = res.get('stdout', [])
            if isinstance(stdout, list):
                stdout = '\n'.join(stdout)
            if stdout:
                for line in stdout.splitlines():
                    self._display.display(f'  {line}', color=C.COLOR_ERROR)

        if ignore_errors:
            self._display.display('  ...ignoring', color=C.COLOR_SKIP)

    # ── runner: SKIPPED ───────────────────────────────────────────────────────

    def v2_runner_on_skipped(self, result):
        pass

    # ── runner: UNREACHABLE ───────────────────────────────────────────────────

    def v2_runner_on_unreachable(self, result):
        host    = result._host.get_name()
        task    = result._task
        msg     = result._result.get('msg', 'host unreachable')
        self._display.display(self._header(task, host, 'UNREACHABLE'), color=C.COLOR_UNREACHABLE)
        self._display.display(f'  {msg}', color=C.COLOR_UNREACHABLE)

        test_id = self._get_test_id(task)
        if test_id and not self._is_cleanup(task):
            self._test_end[test_id] = time.monotonic()
            self._test_status[test_id] = 'FAIL'

    # ── runner: RETRY ─────────────────────────────────────────────────────────

    def v2_runner_retry(self, result):
        host     = result._host.get_name()
        task     = result._task
        attempts = result._result.get('attempts', 0)
        retries  = result._result.get('retries', 0)
        self._display.display(
            f'  {self._name(task)} [{host}] retry {attempts}/{retries}...',
            color=C.COLOR_WARN,
        )

    # ── loop item callbacks ───────────────────────────────────────────────────

    def v2_runner_item_on_ok(self, result):
        self.v2_runner_on_ok(result)

    def v2_runner_item_on_failed(self, result):
        self.v2_runner_on_failed(result)

    def v2_runner_item_on_skipped(self, result):
        pass

    # ── play recap ────────────────────────────────────────────────────────────

    def v2_playbook_on_stats(self, stats):
        self._finalise_test(self._current_test)
        if self._current_test:
            self._print_test_footer(self._current_test)

        self._display.banner('PLAY RECAP')

        n      = len(self._test_order)
        passed = sum(1 for s in self._test_status.values() if s == 'PASS')
        failed = sum(1 for s in self._test_status.values() if s == 'FAIL')
        total  = _fmt_time(time.monotonic() - self._play_start) if self._play_start else '?'
        color  = C.COLOR_ERROR if failed else C.COLOR_OK

        if n:
            for test_id in self._test_order:
                status = self._test_status.get(test_id, 'PASS')
                tc = C.COLOR_ERROR if status == 'FAIL' else C.COLOR_OK
                self._display.display(f'  {test_id:<20} {status}', color=tc)
            self._display.display('')
            summary = f'  {n} {"test" if n == 1 else "tests"}   {passed} passed   {failed} failed   total {total}'
            self._display.display(summary, color=color)
            self._display.display('')

        for h in sorted(stats.processed.keys()):
            t = stats.summarize(h)
            if t['unreachable']:
                self._display.display(f'  {h}   UNREACHABLE', color=C.COLOR_UNREACHABLE)
            elif t['failures']:
                self._display.display(f'  {h}   FAILED', color=C.COLOR_ERROR)
            else:
                self._display.display(f'  {h}   ok', color=C.COLOR_OK)
