"""分析报告导出服务。

把 AI 总结（Markdown）+ 选中的数据包表格渲染为独立 HTML 报告，
供用户下载保存。
"""
from __future__ import annotations

import html
import time
from typing import Any

import markdown as md_lib


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def render_report_html(
    title: str,
    summary_markdown: str,
    packets: list[dict],
    pcap_file: str = "",
    filter_expr: str = "",
) -> str:
    """渲染一份自包含的 HTML 分析报告。"""
    summary_html = md_lib.markdown(
        summary_markdown or "",
        extensions=["fenced_code", "tables"],
    )

    rows_html = ""
    for p in packets:
        rows_html += (
            "<tr>"
            f"<td>{_esc(p.get('number'))}</td>"
            f"<td>{_esc(p.get('time'))}</td>"
            f"<td>{_esc(p.get('source'))}</td>"
            f"<td>{_esc(p.get('destination'))}</td>"
            f"<td>{_esc(p.get('protocol'))}</td>"
            f"<td>{_esc(p.get('length'))}</td>"
            f"<td>{_esc(p.get('info'))}</td>"
            "</tr>\n"
        )

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
  body {{ font-family: 'Segoe UI','Microsoft YaHei',sans-serif; background:#1a1b26; color:#c0caf5;
         max-width: 1000px; margin: 0 auto; padding: 32px 24px; line-height:1.6; }}
  h1 {{ background: linear-gradient(90deg,#7aa2f7,#bb9af7); -webkit-background-clip:text;
        background-clip:text; color:transparent; }}
  .meta {{ color:#7982a9; font-size:13px; margin-bottom:24px; }}
  .meta span {{ margin-right:18px; }}
  .card {{ background:#1f2335; border:1px solid #3b4261; border-radius:10px; padding:20px 24px; margin-bottom:24px; }}
  h2 {{ color:#7aa2f7; border-bottom:1px solid #3b4261; padding-bottom:8px; }}
  table {{ width:100%; border-collapse:collapse; font-family:Consolas,monospace; font-size:12px; }}
  th {{ background:#24283b; color:#7982a9; text-align:left; padding:8px; }}
  td {{ padding:6px 8px; border-bottom:1px solid #2a2f45; }}
  code {{ background:#24283b; padding:2px 6px; border-radius:4px; }}
  .footer {{ color:#565f89; font-size:12px; text-align:center; margin-top:32px; }}
</style>
</head>
<body>
  <h1>🦈 {_esc(title)}</h1>
  <div class="meta">
    <span>生成时间：{now}</span>
    <span>抓包文件：{_esc(pcap_file) or '(未指定)'}</span>
    <span>过滤器：{_esc(filter_expr) or '(无)'}</span>
    <span>数据包数：{len(packets)}</span>
  </div>

  <div class="card">
    <h2>AI 分析报告</h2>
    {summary_html}
  </div>

  <div class="card">
    <h2>数据包明细</h2>
    <table>
      <thead><tr>
        <th>No.</th><th>Time</th><th>Source</th><th>Destination</th>
        <th>Protocol</th><th>Length</th><th>Info</th>
      </tr></thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <div class="footer">由 Wireshark 智能分析助手生成</div>
</body>
</html>"""
