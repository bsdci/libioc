#!/bin/sh
set -e
set -u
set -x
JAIL_NIC=${JAIL_NIC:-vtnet0}
JAIL_IP=${JAIL_IP:-172.16.0}
JAIL_NET=${JAIL_IP:-16}

echo "libiocage regression tests"
yes "" | ioc fetch
ioc list --release --no-header --output-format=list | grep -q 11.1-RELEASE
# fetch older release:
ioc fetch --release 10.4-RELEASE
ioc list --release --no-header --output-format=list | grep -q 10.4-RELEASE

# create a template
ioc create --basejail --name tpl-web ip4_addr="$JAIL_NIC|$JAIL_IP.2/$JAIL_NET"
ioc start tpl-web
ioc exec tpl-web env ASSUME_ALWAYS_YES=YES pkg bootstrap
ioc exec tpl-web env ASSUME_ALWAYS_YES=YES pkg install -y apache24
ioc stop tpl-web
ioc set template=yes tpl-web

# template from 10.4-RELEASE
ioc create --basejail --name tpl-db --release 10.4-RELEASE ip4_addr="$JAIL_NIC|$JAIL_IP.3/$JAIL_NET"
ioc start tpl-db
ioc exec tpl-db env ASSUME_ALWAYS_YES=YES pkg bootstrap
ioc exec tpl-db env ASSUME_ALWAYS_YES=YES pkg install -y mysql57-server
ioc stop tpl-db
ioc set template=yes tpl-db

ioc create --basejail --template tpl-db --name db01 boot=yes ip4_addr="$JAIL_NIC|$JAIL_IP.4/$JAIL_NET"
ioc create --basejail --template tpl-db --name db02 boot=yes ip4_addr="$JAIL_NIC|$JAIL_IP.5/$JAIL_NET"
ioc start 'db0*'
ioc list --no-header --output-format=list | grep -c db0 | grep -qw 2

ioc create --basejail --template tpl-web --name web01 ip4_addr="$JAIL_NIC|$JAIL_IP.6/$JAIL_NET"
ioc create --basejail --template tpl-web --name web02 ip4_addr="$JAIL_NIC|$JAIL_IP.7/$JAIL_NET"
ioc start 'web0*'
ioc list --no-header --output-format=list | grep -c web0 | grep -qw 2

# stop all
ioc stop '*'

# cleanup
ioc destroy --force '*01'
yes | ioc destroy '*02'
# sleep for (u)mounts to settle:
sleep 2
ioc destroy --force template=yes

# cleanup
yes | ioc destroy --release 10.4-RELEASE
ioc destroy --force --release 11.1-RELEASE
