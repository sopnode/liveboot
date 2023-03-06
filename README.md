# todo

* in `/srv/shares/bootable-images/`, name the fedora outputs as `liveboot`
* in `/srv/shares/bootable-images/`, name the fedora outputs after releasever


# booting vanilla OSes live using redfish

goal is for a user to be able to boot a sopnode with a live session of an OS of
their choice; for starters we have ubuntu LTS 18 20 and 22, and fedora rawhide
39

expected (stuff to test):

* can enter ssh as root using our ssh keys
* can reboot gracefully

plus:

* we don't care too much about the state of the console during that time
* it's OK if the console is stuck at the installation program, as long as, of
course, no installation takes places
* in general we can easily open a shell from the console; that's OK too, and
  actually useful esp. at the begining of this project as we often need to
  inspect the current state, sometimes with no ssh available

## strategy

* build a `cloud-init` capable live image for the target distribution
  * fedora: use `livecd-creator`
  * ubuntu: use the upstream public image and tweak its grub config
* build a cloud-init config that contains our ssh keys
* expose these 2 ISOs using redfish virtual media, and boot from there
* the HHD-installed fedora37 can still be used if needed

## setup on sopnode-l1

using this box as a gatekeeper for the sopnode-w* workers

### setup nginx

done manually - see `/etc/nginx/nginx.conf`
expose folder `/srv/shares/bootable-images/` as <http://sopnode-l1.inria.fr/bootable-images/>

### fetch some images

as far as ubuntu, we start from the publicly available so-called live-server images

```bash
# on l1
cd /srv/shares/bootable-images
# see .url files
```

### setup samba

also done; however it is no longer needed since with idrac v6.x we can use both virtual media slots  over http to expose the ISO and the cloud-init config

using the ansible collection here
<https://github.com/vladgh/ansible-collection-vladgh-samba>

we create a samba service on the sopnode-l1 server, where we will
store bootable images

```bash
ansible-playbook -i sopnodes-inventory -K setup-samba-playbook.yml
```

## on sopnode-w3 (setup)

* enabled life cycle manager in the BIOS
(not quite sure yet if that's mandatory, but it does feel that way)

* iDrac firmware version was 5.10.50.00, upgraded to 6.x  
  (its other siblings are all upgraded as well)

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

```shell
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

## ubuntu

1st and foremost objective is to create an ssh-reachable admin user that we can later on use with ansible

### cloud-init images

based on <https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html#creating-a-disk>

```shell
# create an ISO image suitable for cloud-init
seed-cloud-init.sh /srv/shares/bootable-images/cidata-seed.iso cloud-init-template.yaml
```

### liveboot image

we patch the standard ubuntu image, e.g.

```shell
# from https://releases.ubuntu.com/22.04/ubuntu-22.04.2-live-server-amd64.iso
-rw-r--r-- 1 root root 1474873344 Feb 16 15:41 ubuntu-22.04.1-live-server-amd64.iso
```

using our home-brewed tool like so

```shell
./patch-ubuntu-image.sh /srv/shares/bootable-images/ubuntu-22.04.2-live-server-amd64.iso
```

### of interest for troubleshooting

* use Alt-F2 to get a login shell without the password
* https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html
* https://cloudinit.readthedocs.io/en/latest/howto/bugs.html#collect-logs

### status

* 22: OK
* 20: kind of OK
  * the console is stuck at 'select your language' (harmless)
  * **HOWEVER** when rebooting the system enters an endless loop of squashfs error
* 18: OK as well

### epilogue: `livefs-editor` ?

should we switch to using livefs-editor

see also https://github.com/mwhudson/livefs-editor/issues/31

## fedora

here's what we need:

https://docs.fedoraproject.org/en-US/quick-docs/creating-and-using-a-live-installation-image/#proc_creating-and-using-live-cd

here again, working from sopnode-l1

### prerequisites

```shell
dnf install livecd-tools fedora-kickstarts pykickstart
```

### f37

inspired from <https://www.spinics.net/linux/fedora/fedora-users/msg516742.html>

```bash
cd fedora
# xxx argument not yet used
build-fedora-liveboot.sh 37
```

the `-original.ks` file is kept in the repo for the record only; it is the output of

```bash
ksflatten -c /usr/share/spin-kickstarts/fedora-liveboot.ks -o fedora-liveboot-original.ks
```

and the other file has been edited manually from there, mostly in order to
* use the local `fedora-serv` repo
* and the right version of fedora
* enable `cloud-init`
* turn off `ModemManager`, for cosmetic reason only, this is not important

the process if rather long, as it actually builds an image from scratch for us
however it uses cloud-init at run time so we only need to do it once, and the ssh keys
actually used will come from the `cidata` image

see also <https://github.com/livecd-tools/livecd-tools>

### status

* works with rawhide
* scripting for fedora37
* need to check alterative versions as well ?
