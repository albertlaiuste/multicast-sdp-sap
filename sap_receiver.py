import socket, struct

SAP_GRP, SAP_PORT = "224.2.127.254", 9875

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("", SAP_PORT))
mreq = struct.pack("=4s4s", socket.inet_aton(SAP_GRP), socket.inet_aton("0.0.0.0"))
s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

print("Listening for SAP…")
seen = {}

while True:
    pkt, _ = s.recvfrom(65535)
    if len(pkt) < 8:
        continue

    b0, auth_len, msg_id = struct.unpack("!BBH", pkt[:4])
    deletion = (b0 >> 2) & 1
    off = 4 + 4  # skip IPv4 source
    off += auth_len * 4
    sdp = pkt[off:].decode("utf-8", "replace").strip()

    if deletion:
        seen.pop(msg_id, None)
        print(f"Deleted {msg_id}")
        continue

    if msg_id not in seen:
        seen[msg_id] = sdp
        title = None
        for line in sdp.splitlines():
            if line.startswith("s="):
                title = line[2:].strip()
                break
        fname = (title or f"session_{msg_id}").replace(" ", "_") + ".sdp"
        with open(fname, "w") as f:
            f.write(sdp + "\n")
        print(f"New: {title or msg_id} → wrote {fname}")

