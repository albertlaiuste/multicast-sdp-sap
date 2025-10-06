#!/bin/bash

# Play an RTP session described by SDP.
# Usage:
#   ./client_sdp.sh <sdp-file>
#   cat session.sdp | ./client_sdp.sh -

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <sdp-file|->" >&2
  exit 1
fi

SRC=$1

if [[ "$SRC" == "-" ]]; then
  exec gst-launch-1.0 -v \
    fdsrc fd=0 ! sdpdemux name=demux \
    demux. ! rtpjitterbuffer ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false
else
  if [[ ! -f "$SRC" ]]; then
    echo "SDP file not found: $SRC" >&2
    exit 2
  fi
  exec gst-launch-1.0 -v \
    filesrc location="$SRC" ! sdpdemux name=demux \
    demux. ! rtpjitterbuffer ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false
fi

