# scratchpad

miscell notes in no particular order

## console

we don't care too much about the state of the console during the liveboot session:

* it's OK if the console is stuck at the installation program, as long as,
of course, no actual installation takes places
* in general we can easily open a shell from the console; that's OK too, and
actually useful esp. at the begining of this project as we often need to
inspect the current state, sometimes with no ssh available

## setup on sopnode-l1 (the gatekeeper)

using this box as a gatekeeper for the sopnode-w* workers

### setup nginx

done manually - as opposed to using ansible - see `/etc/nginx/nginx.conf`

expose folder `/srv/shares/bootable-images/` as <http://sopnode-l1.inria.fr/bootable-images/>

this is the location where OS images are stored, so the nginx server exposes them over http

### fetch some images

as far as ubuntu, we start from the publicly available so-called live-server images

```bash
# on l1
cd /srv/shares/bootable-images/public
# see .url files
```

## on sopnode-w3 (the nodes)

* on w3: enabled life cycle manager in the BIOS
(not quite sure yet if that's mandatory, but it does feel that way)

* iDrac firmware version was 5.10.50.00, upgraded to 6.x
  (its other siblings are all upgraded as well)

***
***
***



***
***
***



## archive section

### setup samba on sopnode-l1

also done; however it is **no longer needed** since with idrac v6.x we can use
both virtual media slots to expose the ISO **and** the cloud-init config **over http**

so for the record only:

using the ansible collection here
<https://github.com/vladgh/ansible-collection-vladgh-samba>

we create a samba service on the sopnode-l1 server, where we will
store bootable images

```bash
ansible-playbook -i sopnodes-inventory -K setup-samba-playbook.yml
```

## basics of redfish

leverage redfish Python scripts from here
<https://github.com/dell/iDRAC-Redfish-Scripting>
to redirect sopnode-w* to boot off these images

```bash
# this is where I run the stuff
sopnode-l1@root ~/kube-redfish (master=) $
# and this file contains helpful shortcuts
source aliases
# FYI Dell's repo is cloned into a separate repo, and the python scripts are here:
# (cd iD*/*on; pwd)
# /root/kube-redfish/iDRAC-Redfish-Scripting/Redfish Python
```

see aliases for the extended version - we use the aliases only here

### `power` - `GetSetPowerStateREDFISH.py`

```bash
power3 --get
power3 --set GracefulRestart
power3 --set ForceRestart
```

### `media` - `InsertEjectVirtualMediaREDFISH.py`

it feels like only one of 'cd' and 'removabledisk' are available at the same time
we try to use the removabledisk to inject the ignition config

```bash
media3 --get
# cleanup
media3 --action eject --index 1
media3 --action eject --index 2
# for example
media3 --action insert --index 1 --uripath  http://138.96.245.50/bootable-images/ubuntu-22.04.1-live-server-amd64-liveboot.iso
media3 --action insert --index 2 --uripath  http://138.96.245.50/bootable-images/cidata-seed.iso
```

### `nextboot` - `SetNextOneTimeBootVirtualMediaDeviceOemREDFISH.py`

```bash
# works also without --reboot
nextboot3 --device 1 --reboot
```

### `nextbootdev` - `SetNextOneTimeBootDeviceREDFISH.py`

```bash
# same as above mostly
nextbootdev --device Hdd --reboot
```

# using iSCSI instead

useful tips in <https://www.server-world.info/en/note?os=Fedora_28&p=iscsi&f=2>


## server

### install server

on l1

```bash
dnf install -y scsi-target-utils
systemctl enable --now tgtd
firewall-cmd --add-service=iscsi-target --permanent
firewall-cmd --reload
```

### setup server

```bash
mkdir /srv/shares/iscsi-images
dd if=/dev/zero of=/srv/shares/iscsi-images/rocky-9.2.img count=0 bs=1 seek=10G
cat > /etc/tgt/conf.d/rocky-9.2.conf << EOF
<target iqn.2023-05.fr.inria.sopnode-l1:dlp.target01>
    # provided device as a iSCSI target
    backing-store /srv/shares/iscsi-images/rocky-9.2.img
    # iSCSI Initiator's IQN you allow to connect
    initiator-name iqn.2023-05.fr.inria.sopnode-w1:www.initiator01
    # authentication info ( set anyone you like for "username", "password" )
    incominguser sopnode onecalvin
</target>
EOF

systemctl restart tgtd
tgtadm --mode target --op show
```

## client

### install client

```bash
dnf -y install iscsi-initiator-utils
```

### setup client

```bash
echo 'InitiatorName=iqn.2023-05.fr.inria.sopnode-w1:www.initiator01' > /etc/iscsi/fake-client.iscsi
sed -i \
   -e 's|^#*node.session.auth.authmethod .*|node.session.auth.authmethod = CHAP|' \
   -e 's|^#*node.session.auth.username .*|node.session.auth.username = sopnode|' \
   -e 's|^#*node.session.auth.password .*|node.session.auth.password = onecalvin|' \
   /etc/iscsi/iscsid.conf
```

### client usage

#### discovery

***IMPORTANT*** the `--login` option must be passed the first time around

```bash
iscsiadm -m discovery -t sendtargets -p 138.96.245.50 --login
# and then later on this is enough
iscsiadm -m discovery -t sendtargets -p 138.96.245.50
```

the `--logout` option exists but is not supported for discovery mode;

#### connecting as a virtual disk drive

```shell
# for now I have a single target, so no need to say which one...
iscsiadm -m node --login
# dmesg shows me that the volume is available as `/dev/sdb`
```

## building a bootable image

- [ ] download a bootable rocky ISO image from <https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9.2-x86_64-minimal.iso>
- [ ] VirtualBox
  - [ ] create new VM
  - [ ] skip unattended install
  - [ ] enable EFI
  - [ ] create a virtual hard disk: 20 Gb
  - [ ] manual install, reboot
   - [ ] note that <https://github.com/intel/intelRSD/issues26> says the iscsi module needs further settings
  - [ ] however, as a first attempt, no further tweak
  - [ ] turn off the machine
- [ ] converts VBox image into a `.raw` format

  ```bash
  VBoxManage clonehd rocky-9.2.vdi rocky-9.2-01.raw --format RAW
  ```
- rsync'ed the .raw onto `sopnode-l1` in `/srv/shares/iscsi-images`

here's what the automatic partitioning gave me

```console
fdisk -l /dev/sdb
Disk /dev/sdb: 20 GiB, 21474836480 bytes, 41943040 sectors
Disk model: VIRTUAL-DISK
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 4096 bytes
I/O size (minimum/optimal): 4096 bytes / 4096 bytes
Disklabel type: gpt
Disk identifier: 065E1908-3D81-4D06-A3C5-96378473DDF8

Device       Start      End  Sectors  Size Type
/dev/sdb1     2048  1230847  1228800  600M EFI System
/dev/sdb2  1230848  3327999  2097152    1G Linux filesystem
/dev/sdb3  3328000 41940991 38612992 18.4G Linux LVM
```

## booting off that image

sopnode-l1 = 138.96.245.50

playing with many different settings

* seems like the NIC interface MUST have its virtualization mode set
* set the boot mode to UEFI (really needed?)
* disable PXE on the NIC 
* 
