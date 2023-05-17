# https://askubuntu.com/questions/1390827/how-to-make-ubuntu-autoinstall-iso-with-cloud-init-in-ubuntu-21-10/1391309#1391309
# on fedora, you'll need to
# dnf install xorriso bsdtar

# xxx possible improvement: all this is likely doable with livefs-editor
# git@github.com:mwhudson/livefs-editor.git

DEFAULT_OUTPUT_DIR="/srv/shares/bootable-images/"

function patch-ubuntu() {
    local original="$1"; shift
    local patched="$1"; shift

    # tmp while debugging
    local version=$(basename $original | cut -d- -f2 | cut -d. -f1)

    local TMP=$(mktemp -d /tmp/ubuntu-iso-$version-XXX)
    bsdtar -C $TMP -xf $original

    local grubcfg=$TMP/boot/grub/grub.cfg
    # timeout: how long does the prompt screen wait
    # autoinstall: allow the boot to proceed, as it would otherwise wait for confirmation
    #   NOTE that this is potentially intrusive, originally the behaviour of the cd-rom
    #   is to avoid scratching a disk inadvertently...
    # noprompt: do not prompt to eject the CD on reboot
    # fsck.mode=skip: useful on ubuntu-18, speeds it up entirely
    #   (this is a line of its own in the menuentry)
    # quiet: why not
    # cloud-init=enabled: required on ubuntu18, otherwise won't start
    #   needs to be after the ---
    sed -i \
        -e "s/set timeout=[0-9][0-9]*/set timeout=1/" \
        -e "s|/vmlinuz|/vmlinuz autoinstall noprompt fsck.mode=skip quiet|" \
        -e "s| ---| --- cloud-init=enabled|" \
        $grubcfg

    # bulk options
    xorriso -indev $original -report_el_torito as_mkisofs \
        > $TMP/xorriso.options
    local original_options=$(
         cat $TMP/xorriso.options \
          | grep -v '^-V' \
          | grep -v '^--modification-date' \
        )
    # patch the name
    local name_option=$(grep '^-V' $TMP/xorriso.options \
                | sed -e "/'/'Patched/"
    )
    # compute time
    local modification_date=$(date +%Y%m%d%H%M%S00)
    xorriso -as mkisofs \
        $name_option \
        --modification-date=$modification_date \
        $(eval echo $original_options) \
        -o $patched \
        $TMP

    #echo need to clean $TMP
    # comment for debug
    rm -rf $TMP

     echo $patched

}


function usage() {
    echo "Usage: $COMMAND [-o output-image] [-d output-dir] original-ubuntu.iso"
    exit 1
}

function main() {

    local output_image=""
    local output_dir=""
    while getopts "o:d:h" opt; do
        case $opt in
            o) output_image=$OPTARG ;;
            d) output_dir=$OPTARG ;;
            h) echo $USAGE; exit 0 ;;
            \?)
                echo "Invalid option: -$OPTARG" >&2 ; usage ;;
            :)
                echo "Option -$OPTARG requires an argument." >&2 ; usage ;;
        esac
    done
    shift $((OPTIND-1))

    [[ "$#" == 1 ]] || usage

    local original="$1"
    local basename=$(basename $original)
    local distro=$(cut -d- -f1 <<< $basename)
    local version=$(cut -d- -f2 <<< $basename)

    [[ $distro == ubuntu ]] || { echo $original should be an ubuntu .iso; exit 1; }

    [[ -z "$output_image" ]] && output_image="$distro-$version-liveboot.iso"
    [[ -z "$output_dir" ]] && output_dir=$DEFAULT_OUTPUT_DIR

    [[ -f "$original" ]] || { echo $original should be a file; exit 1; }
    [[ -d "$output_dir" ]] || { echo $output_dir should be a directory; exit 1; }

    local patched=$output_dir/$output_image

    patch-ubuntu $original $patched
}

main "$@"
