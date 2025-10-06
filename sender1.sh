#!/bin/bash

gst-launch-1.0 -v videotestsrc is-live=true pattern=smpte ! \
  video/x-raw,framerate=30/1 ! \
  x264enc tune=zerolatency bitrate=2000 speed-preset=ultrafast key-int-max=30 rc-lookahead=0 ! \
  rtph264pay pt=96 config-interval=1 ! \
  udpsink host=239.255.0.11 port=5004 auto-multicast=true ttl-mc=1 sync=false
