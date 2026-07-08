"""Unit tests for backend/permissions.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.permissions import (
    classify_tool,
    needs_approval,
    is_blocked,
    _classify_shell,
    level_label,
)


class TestClassifyTool:
    def test_read_tools(self):
        assert classify_tool("read_file", {}) == "read"
        assert classify_tool("list_files", {}) == "read"
        assert classify_tool("find_files", {}) == "read"
        assert classify_tool("web_search", {}) == "read"
        assert classify_tool("knowledge_search", {}) == "read"
        assert classify_tool("system_info", {}) == "read"
        assert classify_tool("monitoring_query", {}) == "read"
        assert classify_tool("create_document", {}) == "read"
        assert classify_tool("describe_image", {}) == "read"

    def test_write_tools(self):
        assert classify_tool("write_file", {}) == "write"
        assert classify_tool("delete_file", {}) == "write"
        assert classify_tool("create_directory", {}) == "write"
        assert classify_tool("move_file", {}) == "write"
        assert classify_tool("copy_file", {}) == "write"

    def test_admin_tools(self):
        assert classify_tool("ssh_execute", {}) == "admin"

    def test_docker_list_is_write(self):
        assert classify_tool("docker_manage", {"action": "list"}) == "write"

    def test_docker_other_is_admin(self):
        assert classify_tool("docker_manage", {"action": "start"}) == "admin"
        assert classify_tool("docker_manage", {"action": "stop"}) == "admin"
        assert classify_tool("docker_manage", {}) == "admin"

    def test_unknown_tool_defaults_write(self):
        assert classify_tool("unknown_tool", {}) == "write"
        assert classify_tool("", {}) == "write"


class TestNeedsApproval:
    def test_read_no_approval(self):
        assert needs_approval("read") is False

    def test_write_needs_approval(self):
        assert needs_approval("write") is True

    def test_admin_needs_approval(self):
        assert needs_approval("admin") is True

    def test_blocked_needs_approval(self):
        assert needs_approval("blocked") is True

    def test_unknown_level_needs_approval(self):
        assert needs_approval("unknown") is True


class TestIsBlocked:
    def test_blocked_level(self):
        assert is_blocked("blocked") is True

    def test_other_levels_not_blocked(self):
        assert is_blocked("read") is False
        assert is_blocked("write") is False
        assert is_blocked("admin") is False


class TestClassifyShell:
    def test_read_commands(self):
        assert _classify_shell("uptime") == "read"
        assert _classify_shell("df -h") == "read"
        assert _classify_shell("ls /home") == "read"
        assert _classify_shell("cat /etc/hosts") == "read"
        assert _classify_shell("grep -r foo .") == "read"
        assert _classify_shell("ps aux") == "read"
        assert _classify_shell("nvidia-smi") == "read"

    def test_write_commands(self):
        assert _classify_shell("systemctl restart nginx") == "write"
        assert _classify_shell("docker ps") == "write"
        assert _classify_shell("journalctl -u ssh") == "write"
        assert _classify_shell("curl http://example.com") == "write"

    def test_blocked_patterns(self):
        assert _classify_shell("rm -rf /tmp/foo") == "blocked"
        assert _classify_shell("rmdir /etc") == "blocked"
        assert _classify_shell("shutdown now") == "blocked"
        assert _classify_shell("reboot") == "blocked"
        assert _classify_shell("kill 1234") == "blocked"
        assert _classify_shell("echo x | bash") == "blocked"
        assert _classify_shell("eval $(cmd)") == "blocked"

    def test_empty_command_blocked(self):
        assert _classify_shell("") == "blocked"
        assert _classify_shell("   ") == "blocked"

    def test_unknown_command_blocked(self):
        assert _classify_shell("someweirdcommand") == "blocked"


class TestLevelLabel:
    def test_labels(self):
        assert level_label("read") == "READ"
        assert level_label("write") == "WRITE"
        assert level_label("admin") == "ADMIN"
        assert level_label("blocked") == "BLOCKED"

    def test_unknown_level(self):
        assert level_label("unknown") == "UNKNOWN"
