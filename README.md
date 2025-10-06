# Multicast RTP + SAP

Minimal playground for RTP/H.264 over IPv4 multicast with self-announcing senders (SAP) and simple receivers.

## How It Works
- Each `sender.py` instance sends one RTP/H.264 stream to a multicast group via GStreamer and periodically announces its SDP via SAP (224.2.127.254:9875).
- `sap_discovery.py` listens for SAP, writes each SDP to a file, and expires stale sessions.
- You can play an SDP directly with `client.sh` (from file or stdin).

## Requirements
- Python 3.8+
- GStreamer 1.0 runtime and plugins (`gst-launch-1.0`, `x264enc`, `rtph264pay`, `avdec_h264`)
- Multicast enabled on your LAN/VLAN; IGMP snooping + a querier recommended.

## Usage
### 1) Run a tiny sender (one stream per process)
- Auto-select group from name (239.255.X.Y), port 5004, H.264 PT=96, TTL 1:
  ```sh
  ./sender.py --name "Feed A - Ball" --pattern ball
  ```
- Explicit group/port and faster SAP interval:
  ```sh
  ./sender.py --name "Camera 1" --group 239.255.0.42 --port 5006 --sap-interval 20
  ```
- SSM hint (use 232/8 and specify source IP):
  ```sh
  ./sender.py --name "SSM Feed" --group 232.1.2.3 --source 192.0.2.50
  ```
Notes:
- Default SAP: 3 quick announces on start, then every 20s.
- One unique multicast group per stream is recommended; reusing the same port across different groups is fine.

### 2) Discover sessions via SAP and write SDP files
- Basic (expire after 5 minutes):
  ```sh
  python3 sap_discovery.py --expire-sec 300 --output-dir ./sessions
  ```

### 3) Play a session from SDP
- From a file:
  ```sh
  ./client.sh ./sessions/Feed_A_-_Ball.sdp
  ```
- From stdin:
  ```sh
  cat ./sessions/Feed_A_-_Ball.sdp | ./client.sh -
  ```

## Best Practices
- Addressing: Use admin-scoped IPv4 multicast (239/8). For SSM, use 232/8 with IGMPv3.
- Scope: Keep TTL low (e.g., 1) unless you intend to cross routers.
- Switching: Enable IGMP snooping; ensure a querier exists on pure L2 segments.
- Routing: If crossing subnets, enable multicast routing (e.g., PIM-SM/SSM) and verify RPF.

## Files
- `sender.py` — tiny single-stream sender with integrated SAP
- `sap_discovery.py` — listens for SAP, writes SDPs, expires stale sessions
- `client.sh` — plays any SDP (file or stdin) with `sdpdemux`
