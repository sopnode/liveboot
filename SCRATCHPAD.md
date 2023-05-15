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
