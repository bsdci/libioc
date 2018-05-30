#!/bin/sh
set -e
set -u
set -x
JAIL_NIC=${JAIL_NIC:-vtnet0}
JAIL_IP=${JAIL_IP:-172.16.0}
JAIL_NET=${JAIL_IP:-16}
IOCAGE_DATASET=${IOCAGE_DATASET:-zroot/iocage-regression-test}
IOCAGE_MOUNTPOINT=${IOCAGE_MOUNTPOINT:-/iocage-regression-test}
IOC_COMMAND="python3.6 . --source ioc=$IOCAGE_DATASET"

echo "libiocage regression tests"

echo "preparing host"
zfs create -o mountpoint="$IOCAGE_MOUNTPOINT" "$IOCAGE_DATASET" || zfs set mountpoint="$IOCAGE_MOUNTPOINT" "$IOCAGE_DATASET"

echo "fetch default release:"
yes "" | $IOC_COMMAND fetch
$IOC_COMMAND list --release --no-header --output-format=list | grep -q 11.1-RELEASE
echo "fetch older release"
$IOC_COMMAND fetch --release 10.4-RELEASE
$IOC_COMMAND list --release --no-header --output-format=list | grep -q 10.4-RELEASE

echo "create a template"
$IOC_COMMAND create --basejail --name tpl-web ip4_addr="$JAIL_NIC|$JAIL_IP.2/$JAIL_NET"
$IOC_COMMAND start tpl-web
$IOC_COMMAND exec tpl-web env ASSUME_ALWAYS_YES=YES pkg bootstrap
$IOC_COMMAND exec tpl-web pkg install -y apache24
$IOC_COMMAND stop tpl-web
$IOC_COMMAND set template=yes tpl-web

echo "template from 10.4-RELEASE"
$IOC_COMMAND create --basejail --name tpl-db --release 10.4-RELEASE ip4_addr="$JAIL_NIC|$JAIL_IP.3/$JAIL_NET"
$IOC_COMMAND start tpl-db
$IOC_COMMAND exec tpl-db env ASSUME_ALWAYS_YES=YES pkg bootstrap
$IOC_COMMAND exec tpl-db env pkg install -y mysql57-server
$IOC_COMMAND stop tpl-db
$IOC_COMMAND set template=yes tpl-db

$IOC_COMMAND create --basejail --template tpl-db --name db01 boot=yes ip4_addr="$JAIL_NIC|$JAIL_IP.4/$JAIL_NET"
$IOC_COMMAND create --basejail --template tpl-db --name db02 boot=yes ip4_addr="$JAIL_NIC|$JAIL_IP.5/$JAIL_NET"
$IOC_COMMAND start 'db0*'
$IOC_COMMAND list --no-header --output-format=list | grep -c db0 | grep -qw 2

$IOC_COMMAND create --basejail --template tpl-web --name web01 ip4_addr="$JAIL_NIC|$JAIL_IP.6/$JAIL_NET"
$IOC_COMMAND create --basejail --template tpl-web --name web02 ip4_addr="$JAIL_NIC|$JAIL_IP.7/$JAIL_NET"
$IOC_COMMAND start 'web0*'
$IOC_COMMAND list --no-header --output-format=list | grep -c web0 | grep -qw 2

echo "stop all"
$IOC_COMMAND stop '*'

echo "cleanup"
$IOC_COMMAND destroy --force '*01'
yes | $IOC_COMMAND destroy '*02'
$IOC_COMMAND destroy --force template=yes

yes | $IOC_COMMAND destroy --release 10.4-RELEASE
$IOC_COMMAND destroy --force --release 11.1-RELEASE

zfs destroy -r "$IOCAGE_DATASET"
