#!/bin/bash

# refactor for both fedora and rocky

COMMAND=$(basename $0)
DIR=$(dirname $0)
cd $DIR


DEFAULT_OUTPUT_DIR=/srv/shares/bootable-images

function usage() {
    echo "Usage: $COMMAND [-i ks-file] [-d output-dir] [-o image-name] distro"
    echo "  distro: e.g. f38 or r9.1"
    echo "  -i: path to kickstart file"
    echo "  -o: name of output image"
    echo "  -d: path to output directory (default: $DEFAULT_OUTPUT_DIR)"
    echo "  -h: show this help"
    exit 1
}

function main() {
    while getopts "i:d:o:h" opt; do
        case $opt in
            i) KS_FILE=$OPTARG ;;
            o) IMAGE_NAME=$OPTARG ;;
            d) OUTPUT_DIR=$OPTARG ;;
            h) usage exit 0 ;;
            \?)
                echo "Invalid option: -$OPTARG" >&2 ; usage ;;
            :)
                echo "Option -$OPTARG requires an argument." >&2 ; usage ;;
        esac
    done

    shift $((OPTIND-1))

    if [[ $# -ne 1 ]]; then
        echo "Missing distro argument" >&2
        usage
    fi

    DISTRO=$1
    case $DISTRO in
        f*)
            DISTRO_NAME=fedora
            DISTRO_VERSION=${DISTRO#f}
            ;;
        r*)
            DISTRO_NAME=rocky
            DISTRO_VERSION=${DISTRO#r}
            ;;
        *)
            echo "Invalid distro: $DISTRO" >&2
            usage
            ;;
    esac

    [[ -z $KS_FILE ]] && KS_FILE=${DISTRO_NAME}-liveboot.ks
    [[ -z $OUTPUT_DIR ]] && OUTPUT_DIR=$DEFAULT_OUTPUT_DIR
    [[ -z $IMAGE_NAME ]] && IMAGE_NAME=${DISTRO_NAME}-${DISTRO_VERSION}-liveboot

    echo building for $DISTRO_NAME - releasever=$DISTRO_VERSION
    echo    ks_file=$KS_FILE image=$IMAGE_NAME dir=$OUTPUT_DIR

    build-liveboot $DISTRO_VERSION $KS_FILE $IMAGE_NAME $OUTPUT_DIR
}

function build-liveboot() {
    local releasever="$1"; shift
    local ks_file="$1"; shift
    local imagetag="$1"; shift
    local target_dir="$1"; shift

    livecd-creator \
        --verbose \
        --fslabel $imagetag \
        --title=$imagetag \
        --config=$ks_file \
        --releasever=$releasever \
        --cache=/var/cache/live \

    if [[ -f "$imagetag.iso" ]]; then
        echo moving resulting ISO $imagetag.iso into $target_dir
        mv $imagetag.iso $target_dir
    else
        echo FAILED to produce $imagetag.iso - exiting
        exit 1
    fi
}

main "$@"
