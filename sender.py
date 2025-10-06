#!/usr/bin/env python3

"""
Tiny RTP/H.264 multicast sender with integrated SAP.

Run as many instances as you want, each with its own group/port/name.
Defaults follow best practices for campus/lab multicast (admin-scoped group,
TTL 1, dynamic PT 96). Example usages:

  # Auto-pick group from name (hash), default port 5004, H.264 test pattern
  ./sender.py --name "Feed A - Ball" --pattern ball

  # Explicit group and title
  ./sender.py --group 239.255.0.42 --port 5006 --name "Camera 1"

  # Source-specific multicast (SSM): include sender IP in SDP via source-filter
  ./sender.py --group 232.1.2.3 --source 192.0.2.50 --name "SSM Feed"

Stop with Ctrl-C.
"""

import argparse
import contextlib
import hashlib
import os
import random
import signal
import socket
import struct
import subprocess
import sys
import time


SAP_GRP = "224.2.127.254"
SAP_PORT = 9875


def default_outbound_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))  # no traffic sent; used to select interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def group_from_name(name: str) -> str:
    """Derive a 239.255.X.Y group from a session name, stable across runs."""
    h = hashlib.sha1(name.encode("utf-8")).digest()
    x = h[0]
    y = h[1]
    return f"239.255.{x}.{y}"


def make_sdp(name: str, group: str, port: int, pt: int, enc: str, clock: int,
             profile_level_id: str, source_ip: str | None, ttl: int) -> bytes:
    # Connection line: for IPv4 multicast, include TTL. Many stacks ignore it but it's correct per RFC 4566.
    conn = f"c=IN IP4 {group}/{ttl}"
    lines = [
        "v=0",
        f"o=sender 1 1 IN IP4 {source_ip or default_outbound_ip()}",
        f"s={name}",
        f"i={enc} RTP",
        "t=0 0",
        conn,
        f"m=video {port} RTP/AVP {pt}",
        f"a=rtpmap:{pt} {enc}/{clock}",
        f"a=fmtp:{pt} packetization-mode=1;profile-level-id={profile_level_id}",
    ]
    # Optional SSM hint in SDP (some clients ignore; harmless for ASM)
    if source_ip:
        lines.append(f"a=source-filter: incl IN IP4 {group} {source_ip}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def sap_header(sdp_bytes: bytes, src_ipv4: str) -> bytes:
    V, A, R, T, E, C = 1, 0, 0, 0, 0, 0
    b0 = (V << 5) | (A << 4) | (R << 3) | (T << 2) | (E << 1) | C
    auth_len = 0
    msg_id = int.from_bytes(hashlib.sha1(sdp_bytes).digest()[:2], "big")
    return struct.pack("!BBH", b0, auth_len, msg_id) + socket.inet_aton(src_ipv4)


def run_pipeline(group: str, port: int, pt: int, pattern: str, bitrate_kbps: int, ttl: int) -> subprocess.Popen:
    cmd = [
        "gst-launch-1.0", "-v",
        "videotestsrc", "is-live=true", f"pattern={pattern}", "!",
        "video/x-raw,framerate=30/1", "!",
        "x264enc", "tune=zerolatency", f"bitrate={bitrate_kbps}",
        "speed-preset=ultrafast", "key-int-max=30", "rc-lookahead=0", "!",
        "rtph264pay", f"pt={pt}", "config-interval=1", "!",
        "udpsink", f"host={group}", f"port={port}", "auto-multicast=true",
        f"ttl-mc={ttl}", "sync=false",
    ]
    print("Launching:", " ".join(cmd))
    return subprocess.Popen(cmd)


def send_sap_loop(name: str, sdp: bytes, src_ip: str, interval: float):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    pkt = sap_header(sdp, src_ip) + sdp

    # quick startup announcements
    for _ in range(3):
        s.sendto(pkt, (SAP_GRP, SAP_PORT))
        time.sleep(1)

    while True:
        s.sendto(pkt, (SAP_GRP, SAP_PORT))
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="Tiny multicast RTP sender with SAP")
    ap.add_argument("--name", required=True, help="Session name for SAP/SDP")
    ap.add_argument("--group", help="Multicast group (IPv4). Default derived from name in 239.255.0.0/16")
    ap.add_argument("--port", type=int, default=5004, help="UDP port for RTP (default: 5004)")
    ap.add_argument("--pt", type=int, default=96, help="RTP payload type (default: 96)")
    ap.add_argument("--pattern", default="smpte", help="videotestsrc pattern (default: smpte)")
    ap.add_argument("--bitrate", type=int, default=2000, help="Video bitrate kbps (default: 2000)")
    ap.add_argument("--ttl", type=int, default=1, help="Multicast TTL/hops (default: 1)")
    ap.add_argument("--enc", default="H264", help="Encoding name for rtpmap (default: H264)")
    ap.add_argument("--clock", type=int, default=90000, help="Clock rate for rtpmap (default: 90000)")
    ap.add_argument("--profile-level-id", default="42e01f", help="H264 profile-level-id in fmtp")
    ap.add_argument("--source", help="Source IP for SSM SDP (optional)")
    ap.add_argument("--sap-interval", type=float, default=20.0, help="Seconds between SAP announces (default: 20.0)")
    args = ap.parse_args()

    group = args.group or group_from_name(args.name)
    src_ip = default_outbound_ip()

    sdp = make_sdp(
        name=args.name,
        group=group,
        port=args.port,
        pt=args.pt,
        enc=args.enc,
        clock=args.clock,
        profile_level_id=args.profile_level_id,
        source_ip=args.source or None,
        ttl=args.ttl,
    )

    proc = run_pipeline(group, args.port, args.pt, args.pattern, args.bitrate, args.ttl)

    def shutdown(sig, frame):
        print("\nShutting down sender…")
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            with contextlib.suppress(Exception):
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        send_sap_loop(args.name, sdp, src_ip, args.sap_interval)
    finally:
        shutdown(None, None)


if __name__ == "__main__":
    main()

