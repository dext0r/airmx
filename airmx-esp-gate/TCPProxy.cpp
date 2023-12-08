#include "Arduino.h"
#include <lwip/raw.h>
#include <lwip/inet.h>

#define TCP_PROXY_START_PORT 56000
#define TCP_PROXY_MAX_CONNECTIONS 256
#define TCP_PROXY_MAX_PORTMAP 2

// #define TCP_PROXY_DEBUG
// #define TCP_PROXY_DEBUG_CONNLIST

#ifdef TCP_PROXY_DEBUG
#define DPRINT(...) Serial.print(__VA_ARGS__)
#define DPRINTLN(...) Serial.println(__VA_ARGS__)
#define DPRINTF(...) Serial.printf(__VA_ARGS__)
#else
#define DPRINT(...)
#define DPRINTLN(...)
#define DPRINTF(...)
#endif

struct tcp_proxy_portmap {
  uint16_t proxy_port;
  uint16_t target_port;
};

struct tcp_pseudo_header {
  uint32_t src;
  uint32_t dest;
  uint8_t reserved;
  uint8_t protocol;
  uint16_t tcp_length;
};

struct connection {
  ip_addr_t client_addr;
  uint16_t client_src_port;
  uint16_t client_dest_port;
  uint16_t proxy_src_port;
  uint16_t target_port;
};

struct tcp_proxy {
  struct raw_pcb *pcb;
  uint16_t ignore_port;
  ip_addr_t listen_addr;
  ip_addr_t proxy_addr;
  ip_addr_t target_addr;
  tcp_proxy_portmap portmap[TCP_PROXY_MAX_PORTMAP];
} config;

connection connlist[TCP_PROXY_MAX_CONNECTIONS];
uint16_t conn_idx;

void update_checksum(uint8_t *pkt, ip_addr_t *src_addr, ip_addr_t *dest_addr, int length) {
  struct tcp_pseudo_header pheader;
  uint32_t chksum;
  uint8_t *psum;
  uint16_t finalsum;

  memset(&pheader, 0, sizeof(struct tcp_pseudo_header));

  pheader.src = src_addr->addr;
  pheader.dest = dest_addr->addr;
  pheader.protocol = 6;
  pheader.tcp_length = htons(length);

  pkt[16] = 0;  // checksum
  pkt[17] = 0;
  chksum = 0;
  psum = (uint8_t *)&pheader;
  for (int i = 0; i < 12; i += 2) {
    uint16_t chunk = (psum[0] << 8) | psum[1];
    chksum += chunk;
    psum += 2;
  }

  psum = (uint8_t *)pkt;
  while (length > 1) {
    uint16_t chunk = (*psum << 8) | *(psum + 1);
    chksum += chunk;
    psum += 2;
    length -= 2;
  }

  if (length > 0) {
    uint16_t chunk = (uint16_t)(*psum) << 8;
    chksum += chunk;
  }

  finalsum = (chksum & 0xffff) + (chksum >> 16);

  while (chksum >> 16) {
    chksum = (chksum & 0xffff) + (chksum >> 16);
  }

  chksum = ~chksum;
  finalsum = (uint16_t)chksum;

  pkt[16] = finalsum >> 8;
  pkt[17] = finalsum & 0xff;
}

static uint8_t handle_packet(void *arg, raw_pcb *pcb, pbuf *p, const ip_addr_t *addr) {
  DPRINTLN("tcpproxy: handle packet");
  if (pcb == nullptr || p == nullptr || addr == nullptr) {
    DPRINTLN("tcpproxy: skip packet");
    return 0;
  }

  struct ip_hdr *pkt_ip_hdr = (struct ip_hdr *)p->payload;
  if (pkt_ip_hdr == nullptr) {
    DPRINTLN("tcpproxy: error 2");
    return 0;
  }

  ip_addr_t pkt_src_addr;
  ip_addr_t pkt_dest_addr;
  ip_addr_copy(pkt_src_addr, pkt_ip_hdr->src);
  ip_addr_copy(pkt_dest_addr, pkt_ip_hdr->dest);

  uint8_t *pkt = (uint8_t *)p->payload;
  uint16_t pkt_src_port = (pkt[20] << 8) | pkt[21];
  uint16_t pkt_dest_port = (pkt[22] << 8) | pkt[23];

  DPRINTF("tcpproxy: %s:%d", inet_ntoa(pkt_src_addr), pkt_src_port);
  DPRINTF(" -> %s:%d \n", inet_ntoa(pkt_dest_addr), pkt_dest_port);

  if (pkt_dest_port == config.ignore_port || pkt_src_port == config.ignore_port) {
    return 0;
  }

  bool pkt_from_client = (pkt_src_addr.addr != config.target_addr.addr && pkt_dest_addr.addr == config.listen_addr.addr);
  bool pkt_from_target = (pkt_src_addr.addr == config.target_addr.addr);
  DPRINTF("tcpproxy: pkt_from_client %d, pkt_from_target %d\n", pkt_from_client ? 1 : 0, pkt_from_target ? 1 : 0);
  if (!pkt_from_client && !pkt_from_target) {
    return 0;
  }

  pbuf_header(p, -PBUF_IP_HLEN);
  connection *conn = NULL;
  for (int i = 0; i <= TCP_PROXY_MAX_CONNECTIONS - 1; i++) {
    connection *estb_conn = &connlist[i];

#ifdef TCP_PROXY_DEBUG_CONNLIST
    DPRINTF("%d: %s:%d/%d -> %d/%d\n",
            i,
            inet_ntoa(estb_conn->client_addr),
            estb_conn->client_src_port,
            estb_conn->client_dest_port,
            estb_conn->proxy_src_port,
            estb_conn->target_port);
#endif

    if (pkt_from_client && estb_conn->client_addr.addr == pkt_src_addr.addr && estb_conn->client_src_port == pkt_src_port) {
      conn = estb_conn;
      break;
    }
    if (pkt_from_target && estb_conn->proxy_src_port == pkt_dest_port && estb_conn->target_port == pkt_src_port) {
      conn = estb_conn;
      break;
    }
  }

  if (!conn && pkt_from_client) {
    DPRINTLN("tcpproxy: new connection");
    conn_idx++;
    if (conn_idx >= TCP_PROXY_MAX_CONNECTIONS) {
      conn_idx = 0;
    }

    conn = &connlist[conn_idx];
    conn->client_addr = pkt_src_addr;
    conn->client_src_port = pkt_src_port;
    conn->proxy_src_port = TCP_PROXY_START_PORT + conn_idx;

    DPRINTF("tcpproxy: new [%d] %s:%d -> %d:%d\n",
            conn_idx,
            inet_ntoa(conn->client_addr),
            conn->proxy_src_port,
            conn->client_src_port,
            pkt_dest_port);
  }

  if (conn && pkt_from_client) {
    conn->client_dest_port = pkt_dest_port;

    conn->target_port = pkt_dest_port;
    for (int i = 0; i < TCP_PROXY_MAX_PORTMAP; i++) {
      tcp_proxy_portmap *pmap = &config.portmap[i];
      if (pmap->proxy_port == pkt_dest_port) {
        conn->target_port = pmap->target_port;
      }
    }

    if (conn->target_port == pkt_dest_port) {
      DPRINTLN("tcpproxy: not in portmap");
      return 0;
    }
    
    DPRINTF("tcpproxy: upd [%d]: %d -> %s:%d \n",
            conn_idx,
            conn->proxy_src_port,
            inet_ntoa(config.target_addr),
            conn->target_port);
  }

  if (!conn) {
    DPRINTLN("tcpproxy: ignoring packet, connection not found");
    return 0;
  }

  ip_addr_t pkt_new_dest_addr = pkt_from_client ? config.target_addr : conn->client_addr;
  ip_addr_t pkt_new_src_addr = pkt_from_client ? config.proxy_addr : config.listen_addr;
  if (pkt_from_client) {
    // source port
    pkt[20] = conn->proxy_src_port >> 8;
    pkt[21] = conn->proxy_src_port & 0xff;
    // destination port
    pkt[22] = conn->target_port >> 8;
    pkt[23] = conn->target_port & 0xff;
  } else {
    // source port
    pkt[20] = conn->client_dest_port >> 8;
    pkt[21] = conn->client_dest_port & 0xff;
    // destination port
    pkt[22] = conn->client_src_port >> 8;
    pkt[23] = conn->client_src_port & 0xff;
  }
  update_checksum((uint8_t *)p->payload, &pkt_new_src_addr, &pkt_new_dest_addr, p->len);

  uint16_t pkt_new_dest_port = (pkt[22] << 8) | pkt[23];
  DPRINTF("tcpproxy: send to %s:%d\n", inet_ntoa(pkt_new_dest_addr), pkt_new_dest_port);
  raw_sendto(config.pcb, p, &pkt_new_dest_addr);

  pbuf_free(p);
  return 1;
}

void tcp_proxy_start(ip_addr_t listen_addr, ip_addr_t target_addr, uint16_t ignore_port) {
  config.ignore_port = ignore_port;
  config.listen_addr = listen_addr;
  config.target_addr = target_addr;

  config.portmap[0].proxy_port = 80;
  config.portmap[0].target_port = 25880;
  config.portmap[1].proxy_port = 1883;
  config.portmap[1].target_port = 25883;

  Serial.printf("tcpproxy started: listen_addr %s", inet_ntoa(config.listen_addr));
  Serial.printf(", target_addr %s\n", inet_ntoa(config.target_addr));

  config.pcb = raw_new(IP_PROTO_TCP);
  if (config.pcb == nullptr) {
    Serial.println("tcpproxy: raw_new failed");
    return;
  }

  raw_recv(config.pcb, handle_packet, NULL);
  raw_bind(config.pcb, IP_ADDR_ANY);
}

void tcp_proxy_set_proxy_addr(ip_addr_t addr) {
  Serial.printf("tcpproxy: set proxy_addr %s\n", inet_ntoa(addr));
  config.proxy_addr = addr;
}