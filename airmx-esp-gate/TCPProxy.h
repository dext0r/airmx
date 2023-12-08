#ifndef TCPPROXY_H
#define TCPPROXY_H
void tcp_proxy_start(ip_addr_t listen_addr, ip_addr_t target_addr, uint16_t skip_port);
void tcp_proxy_set_proxy_addr(ip_addr_t addr);
#endif

