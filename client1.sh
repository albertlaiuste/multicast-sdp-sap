#!/bin/bash

gst-launch-1.0 -v \
  filesrc location=Feed_B_-_SMPTE.sdp ! sdpdemux name=demux \
  demux. ! rtpjitterbuffer ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink sync=false
