// Wireshark 常用显示过滤字段（按协议分组），用于过滤器自动补全。
// 每项：{ field, desc, example? }
export const FILTER_FIELDS = [
  // 帧
  { field: 'frame.number', desc: '帧序号', example: 'frame.number == 100' },
  { field: 'frame.len', desc: '帧长度', example: 'frame.len > 1000' },
  { field: 'frame.time_relative', desc: '相对时间（秒）', example: 'frame.time_relative > 5' },
  // IP
  { field: 'ip.addr', desc: '源或目的 IP', example: 'ip.addr == 192.168.1.1' },
  { field: 'ip.src', desc: '源 IP', example: 'ip.src == 192.168.1.1' },
  { field: 'ip.dst', desc: '目的 IP', example: 'ip.dst == 8.8.8.8' },
  { field: 'ip.proto', desc: 'IP 协议号', example: 'ip.proto == 6' },
  { field: 'ip.ttl', desc: 'TTL', example: 'ip.ttl < 64' },
  // IPv6
  { field: 'ipv6.addr', desc: '源或目的 IPv6', example: 'ipv6.addr == ::1' },
  { field: 'ipv6.src', desc: '源 IPv6', example: 'ipv6.src == fe80::1' },
  { field: 'ipv6.dst', desc: '目的 IPv6', example: 'ipv6.dst == fe80::1' },
  // TCP
  { field: 'tcp', desc: '仅 TCP 包', example: 'tcp' },
  { field: 'tcp.port', desc: '源或目的端口', example: 'tcp.port == 80' },
  { field: 'tcp.srcport', desc: '源端口', example: 'tcp.srcport == 50000' },
  { field: 'tcp.dstport', desc: '目的端口', example: 'tcp.dstport == 443' },
  { field: 'tcp.stream', desc: 'TCP 流索引', example: 'tcp.stream == 0' },
  { field: 'tcp.flags.syn', desc: 'SYN 标志', example: 'tcp.flags.syn == 1' },
  { field: 'tcp.flags.ack', desc: 'ACK 标志', example: 'tcp.flags.ack == 1' },
  { field: 'tcp.flags.fin', desc: 'FIN 标志', example: 'tcp.flags.fin == 1' },
  { field: 'tcp.flags.reset', desc: 'RST 标志', example: 'tcp.flags.reset == 1' },
  { field: 'tcp.analysis.retransmission', desc: 'TCP 重传', example: 'tcp.analysis.retransmission' },
  { field: 'tcp.analysis.lost_segment', desc: 'TCP 丢段', example: 'tcp.analysis.lost_segment' },
  { field: 'tcp.analysis.duplicate_ack', desc: '重复 ACK', example: 'tcp.analysis.duplicate_ack' },
  // UDP
  { field: 'udp', desc: '仅 UDP 包', example: 'udp' },
  { field: 'udp.port', desc: '源或目的端口', example: 'udp.port == 53' },
  { field: 'udp.srcport', desc: '源端口', example: 'udp.srcport == 53' },
  { field: 'udp.dstport', desc: '目的端口', example: 'udp.dstport == 53' },
  { field: 'udp.stream', desc: 'UDP 流索引', example: 'udp.stream == 0' },
  // HTTP
  { field: 'http', desc: '仅 HTTP 包', example: 'http' },
  { field: 'http.request', desc: 'HTTP 请求', example: 'http.request' },
  { field: 'http.request.method', desc: '请求方法', example: 'http.request.method == "GET"' },
  { field: 'http.request.uri', desc: '请求 URI', example: 'http.request.uri contains "/api"' },
  { field: 'http.host', desc: 'Host 头', example: 'http.host contains "baidu"' },
  { field: 'http.response', desc: 'HTTP 响应', example: 'http.response' },
  { field: 'http.response.code', desc: '响应状态码', example: 'http.response.code >= 400' },
  { field: 'http.content_type', desc: 'Content-Type', example: 'http.content_type contains "json"' },
  { field: 'http.user_agent', desc: 'User-Agent', example: 'http.user_agent contains "curl"' },
  // TLS/SSL
  { field: 'tls', desc: '仅 TLS 包', example: 'tls' },
  { field: 'tls.handshake', desc: 'TLS 握手', example: 'tls.handshake' },
  { field: 'tls.handshake.type', desc: '握手类型', example: 'tls.handshake.type == 1' },
  { field: 'tls.handshake.extensions_server_name', desc: 'SNI 域名', example: 'tls.handshake.extensions_server_name contains "google"' },
  // DNS
  { field: 'dns', desc: '仅 DNS 包', example: 'dns' },
  { field: 'dns.qry.name', desc: '查询域名', example: 'dns.qry.name contains "baidu"' },
  { field: 'dns.qry.type', desc: '查询类型', example: 'dns.qry.type == 1' },
  { field: 'dns.flags.response', desc: '是否响应', example: 'dns.flags.response == 1' },
  { field: 'dns.a', desc: 'A 记录答案', example: 'dns.a == 8.8.8.8' },
  // ICMP / ARP
  { field: 'icmp', desc: '仅 ICMP 包', example: 'icmp' },
  { field: 'icmp.type', desc: 'ICMP 类型', example: 'icmp.type == 8' },
  { field: 'arp', desc: '仅 ARP 包', example: 'arp' },
  { field: 'arp.src.proto_ipv4', desc: 'ARP 源 IP', example: 'arp.src.proto_ipv4 == 192.168.1.1' },
  // 逻辑运算符提示
  { field: 'and', desc: '逻辑与', example: 'tcp and ip.addr == 1.1.1.1' },
  { field: 'or', desc: '逻辑或', example: 'tcp or udp' },
  { field: 'not', desc: '逻辑非', example: 'not arp' },
  { field: 'contains', desc: '包含子串', example: 'http.host contains "com"' },
  { field: 'matches', desc: '正则匹配', example: 'http.host matches "\\\\.cn$"' },
]

// 按当前输入的最后一个 token 匹配补全候选。
// 返回 [{field, desc}]，最多 limit 条。
export function getFilterCompletions(input, limit = 8) {
  if (!input) return []
  // 取最后一个非空白/括号片段作为前缀
  const m = input.match(/[A-Za-z0-9_.\-]+$/)
  const prefix = m ? m[0].toLowerCase() : ''
  if (!prefix) return []
  return FILTER_FIELDS
    .filter((f) => f.field.toLowerCase().startsWith(prefix) && f.field.toLowerCase() !== prefix)
    .slice(0, limit)
}
