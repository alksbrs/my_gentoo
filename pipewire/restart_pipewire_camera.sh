#!/bin/bash
# Safe Pipewire + portal restart for OpenRC

# Kill existing
killall -9 pipewire pipewire-pulse wireplumber xdg-desktop-portal xdg-desktop-portal-wlr 2>/dev/null
sleep 2

# Start pipewire with nohup (detached from terminal)
nohup /usr/bin/pipewire > /tmp/pipewire.log 2>&1 &
sleep 1
nohup /usr/bin/pipewire -c pipewire-pulse.conf > /tmp/pipewire-pulse.log 2>&1 &
sleep 1
nohup /usr/bin/wireplumber > /tmp/wireplumber.log 2>&1 &
sleep 2

# Start portals
nohup /usr/libexec/xdg-desktop-portal-wlr > /tmp/portal-wlr.log 2>&1 &
sleep 1
nohup /usr/libexec/xdg-desktop-portal > /tmp/portal.log 2>&1 &
sleep 2

echo "Services restarted. Checking camera node..."
pw-cli ls Node 2>/dev/null | grep -iE "libcamera|ov2740|Internal front camera" | head -5

echo "Checking portal services..."
busctl --user list | grep -i portal | head -5
