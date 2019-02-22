#!/bin/sh
print "Cirrus Ci: populate ZFS pool $POOL"
mkdir -p /pools/
truncate -s 16G "/pools/$POOL.img"
zpool create -m "/.$POOL" "$POOL" "/pools/$POOL.img"
zfs set compression=lz4 "$POOL"
zpool export "$POOL"
