"""单元测试：packet_service / report_service / capture_service。

运行方式：
    cd backend
    python -m pytest tests/ -v
    或
    python tests/test_services.py

说明：
- 不依赖真实 pcap 文件与 tshark（用假对象/猴子补丁模拟）。
- 不调用真实 LLM（网络请求），仅测试纯函数逻辑。
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保 backend/ 在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import report_service  # noqa: E402


# ---------------------------------------------------------------------
# report_service
# ---------------------------------------------------------------------
class TestReportService(unittest.TestCase):
    def test_render_report_html_contains_key_parts(self):
        packets = [
            {"number": 1, "time": "01:00:00.000", "source": "1.1.1.1",
             "destination": "2.2.2.2", "protocol": "TCP", "length": 60, "info": "80 → 443"},
        ]
        html = report_service.render_report_html(
            title="测试报告",
            summary_markdown="## 结论\n一切正常",
            packets=packets,
            pcap_file="test.pcap",
            filter_expr="tcp",
        )
        self.assertIn("测试报告", html)
        self.assertIn("一切正常", html)          # Markdown 已渲染
        self.assertIn("1.1.1.1", html)           # 数据包表格
        self.assertIn("test.pcap", html)
        self.assertIn("<h2>", html)              # Markdown 标题渲染为 HTML

    def test_render_report_html_escapes_html(self):
        packets = [{"number": 1, "time": "", "source": "<script>alert(1)</script>",
                    "destination": "", "protocol": "", "length": 0, "info": ""}]
        html = report_service.render_report_html("t", "s", packets)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


# ---------------------------------------------------------------------
# packet_service 纯函数（不依赖 pyshark/tshark）
# ---------------------------------------------------------------------
class TestPacketServiceHelpers(unittest.TestCase):
    def test_rows_cache_set_get(self):
        from core.packet_service import _RowsCache
        cache = _RowsCache(max_entries=2)
        cache.set(("a", ""), 1.0, [{"number": 1}])
        self.assertEqual(cache.get(("a", ""), 1.0), [{"number": 1}])
        # mtime 变化 -> 缓存失效
        self.assertIsNone(cache.get(("a", ""), 2.0))

    def test_rows_cache_eviction(self):
        from core.packet_service import _RowsCache
        cache = _RowsCache(max_entries=2)
        cache.set(("a", ""), 1.0, [1])
        cache.set(("b", ""), 1.0, [2])
        cache.set(("c", ""), 1.0, [3])  # 触发淘汰
        self.assertEqual(len(cache._data), 2)

    def test_protocol_distribution_uses_cache(self):
        from core import packet_service
        fake_rows = [
            {"protocol": "TCP"}, {"protocol": "TCP"}, {"protocol": "DNS"},
        ]
        with patch.object(packet_service, "_build_all_rows", return_value=fake_rows):
            dist = packet_service.get_protocol_distribution("dummy.pcap")
        self.assertEqual(dist["total"], 3)
        d = {x["protocol"]: x["count"] for x in dist["distribution"]}
        self.assertEqual(d["TCP"], 2)
        self.assertEqual(d["DNS"], 1)
        # 降序排列
        self.assertEqual(dist["distribution"][0]["protocol"], "TCP")

    def test_get_packets_page_slices(self):
        from core import packet_service
        fake_rows = [{"number": i, "protocol": "TCP"} for i in range(1, 251)]
        with patch.object(packet_service, "_build_all_rows", return_value=fake_rows):
            page = packet_service.get_packets_page("dummy.pcap", offset=0, limit=100)
        self.assertEqual(page["total_matched"], 250)
        self.assertEqual(len(page["packets"]), 100)
        self.assertTrue(page["has_more"])
        self.assertEqual(page["packets"][0]["number"], 1)


# ---------------------------------------------------------------------
# capture_service
# ---------------------------------------------------------------------
class TestCaptureService(unittest.TestCase):
    def test_status_unknown_task(self):
        from core import capture_service
        from core.pyshark_analyzer import PysharkAnalyzerError
        with self.assertRaises(PysharkAnalyzerError):
            capture_service.get_capture_status("nonexistent-task-id")


# ---------------------------------------------------------------------
# llm_service 纯函数（不调用真实 LLM）
# ---------------------------------------------------------------------
class TestLlmServiceHelpers(unittest.TestCase):
    def test_summarize_empty_packets(self):
        from core import llm_service
        result = llm_service.summarize_packets([])
        self.assertIn("未提供", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
