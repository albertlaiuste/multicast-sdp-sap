import socket, struct, hashlib, time, random

SAP_GRP, SAP_PORT = "224.2.127.254", 9875
ANN_MIN, ANN_MAX = 60, 120

SDPS = [
    b"""v=0
o=senderA 1 1 IN IP4 192.0.2.10
s=Feed A - Ball
i=H.264 RTP
t=0 0
c=IN IP4 239.255.0.10/32
m=video 5004 RTP/AVP 96
a=rtpmap:96 H264/90000
a=fmtp:96 packetization-mode=1;profile-level-id=42e01f
""",
    b"""v=0
o=senderB 1 1 IN IP4 192.0.2.11
s=Feed B - SMPTE
i=H.264 RTP
t=0 0
c=IN IP4 239.255.0.11/32
m=video 5004 RTP/AVP 96
a=rtpmap:96 H264/90000
a=fmtp:96 packetization-mode=1;profile-level-id=42e01f
""",
]

def sap_header(sdp_bytes, src_ipv4="0.0.0.0"):
    V = 1
    A = 0
    R = 0
    T = 0
    E = 0
    C = 0
    addr_type = 0  # IPv4, announce
    b0 = (V << 5) | (A << 4) | (R << 3) | (T << 2) | (E << 1) | C
    auth_len = 0
    msg_id = int.from_bytes(hashlib.sha1(sdp_bytes).digest()[:2], "big")
    hdr = struct.pack("!BBH", b0, auth_len, msg_id)
    return hdr + socket.inet_aton(src_ipv4)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    pkts = [sap_header(sdp) + sdp for sdp in SDPS]

    for _ in range(3):
        for p in pkts:
            s.sendto(p, (SAP_GRP, SAP_PORT))
        time.sleep(1.0)

    while True:
        for p in pkts:
            s.sendto(p, (SAP_GRP, SAP_PORT))
        time.sleep(random.uniform(ANN_MIN, ANN_MAX))

if __name__ == "__main__":
    main()

