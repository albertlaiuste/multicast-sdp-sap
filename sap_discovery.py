import argparse
import socket
import struct
import threading
import time
from pathlib import Path


SAP_GRP, SAP_PORT = "224.2.127.254", 9875


def parse_title(sdp: str) -> str | None:
    for line in sdp.splitlines():
        if line.startswith("s="):
            return line[2:].strip()
    return None

def main():
    ap = argparse.ArgumentParser(description="SAP receiver that writes SDP files and expires stale entries")
    ap.add_argument("--expire-sec", type=int, default=300, help="Expire sessions not re-announced within this many seconds (default: 300)")
    ap.add_argument("--output-dir", default=".", help="Directory to write SDP files (default: current dir)")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", SAP_PORT))
    mreq = struct.pack("=4s4s", socket.inet_aton(SAP_GRP), socket.inet_aton("0.0.0.0"))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print("Listening for SAP…")

    # msg_id -> info
    seen: dict[int, dict] = {}

    def sweeper():
        while True:
            now = time.time()
            to_delete = []
            for mid, info in list(seen.items()):
                if now - info["last_seen"] > args.expire_sec:
                    to_delete.append(mid)
            for mid in to_delete:
                info = seen.pop(mid, None)
                if info:
                    try:
                        Path(info["path"]).unlink(missing_ok=True)
                    except Exception:
                        pass
                    print(f"Expired: {info['title']} ({mid}) → removed {info['path']}")
            time.sleep(30)

    threading.Thread(target=sweeper, daemon=True).start()

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
            info = seen.pop(msg_id, None)
            if info:
                try:
                    Path(info["path"]).unlink(missing_ok=True)
                except Exception:
                    pass
                print(f"Deleted: {info['title']} ({msg_id}) → removed {info['path']}")
            else:
                print(f"Deleted {msg_id}")
            continue

        title = parse_title(sdp) or f"session_{msg_id}"
        fname = (title.replace(" ", "_")) + ".sdp"
        fpath = str(out_dir / fname)

        first_time = msg_id not in seen
        seen[msg_id] = {
            "title": title,
            "path": fpath,
            "last_seen": time.time(),
            "sdp": sdp,
        }

        if first_time:
            with open(fpath, "w") as f:
                f.write(sdp + "\n")
            print(f"New: {title} → wrote {fpath}")



if __name__ == "__main__":
    main()
