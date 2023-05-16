# a devel utility to try out an image locally on sopnode-l1

# this will run a vnc server on port 5900
# to connect to it through the inria firewall:
# ssh -L localhost:5904:sopnode-l1.inria.fr:5900 root@sopnode-l1.inria.fr
# then connect to localhost:4 with vnc viewer

# requires
# dnf install qemu qemu-kvm qemu-kvm-core
# as well as virtualization enabled in the bios

function clean-qemu() {
    pkill qemu-system
    # lingering socket
    sleep 1
}


function run-qemu() {
    local image="$1"; shift

    qemu-system-x86_64 \
        -m 2048 \
        -boot d \
        -cdrom $image \
        -vnc 138.96.245.50:0 \
        -smp 2 \
        -enable-kvm \
        -cpu host \
        -daemonize \

}

function main() {
    local image="$1"; shift
    # kill previous qemu instances
    clean-qemu
    run-qemu $image
}

main "$@"
