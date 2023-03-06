#!/bin/bash

COMMAND=$(basename $0)
DIR=$(dirname $0)
cd $DIR

function build-liveboot() {
    local releasever="$1"; shift
    local target_dir="$1"; shift

    local stem=f$releasever-sopnode-liveboot

    livecd-creator \
        --verbose \
        --fslabel $stem \
        --title=$stem \
        --config=fedora-liveboot.ks \
        --releasever=$releasever \
        --cache=/var/cache/live \

    if [[ -f "$stem.iso" ]]; then
        echo moving resulting ISO $stem.iso into $target_dir
        mv $stem.iso $target_dir
    else
        echo FAILED to produce $stem.iso - exiting
        exit 1
    fi
}

USAGE="Usage: $COMMAND releasever target-dir"

function main() {

    [[ "$#" == 2 ]] || { echo $USAGE; exit 1; }

    local releasever="$1"; shift
    local target_dir="$1"; shift
    build-liveboot $releasever $target_dir
}

main "$@"
