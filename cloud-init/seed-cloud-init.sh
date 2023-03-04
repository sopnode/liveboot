#!/bin/bash

set -e

COMMAND=$(basename $0)

DEBUG=""

function make-cidata-iso() {

    local stem="$1"; shift
    local keysfile="$1"; shift
    local usertmpl="$1"; shift
    local imagename="$1"; shift

    local MNT=$(mktemp -d /mnt/cidata-mnt-XXX)
    cat > $MNT/meta-data << EOF
instance-id: iid-local01
local-hostname: cloudimg
EOF

    jinja2 -D stem=$stem $usertmpl $keysfile > $MNT/user-data
    # it's important that the volume be named cidata
    genisoimage -output $imagename -volid cidata -joliet -rock $MNT/user-data $MNT/meta-data >& /dev/null

    if [[ -z "$DEBUG" ]]; then
        rm -rf $MNT
    else
        echo DEBUG: $MNT is not removed
    fi
    # echo Done in $imagename
}

USAGE="Usage: $COMMAND stem keysfile user-data-template path-to-seed"

function main() {

    [[ "$#" =~ ^[34]$ ]] || { echo $USAGE; exit 1;}

    # pass e.g. w1
    local stem="$1"; shift
    local keysfile="$1"; shift
    local usertmpl="$1"; shift
    local imagename="$1"; shift

    [[ -z $imagename ]] && imagename="/srv/shares/bootable-images/cidata-seed-${stem}.iso"

    make-cidata-iso $stem $keysfile $usertmpl $imagename
}

main "$@"
