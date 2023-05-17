# booting vanilla OSes live using redfish

goal is for a user to be able to boot a sopnode with a live session of an OS of
their choice; for starters we have ubuntu LTS 18 20 and 22, and fedora 36 and 37

expected (stuff to test):

* can turn boxes on and off
* can reboot on hard disk
* can reboot on vanilla image for some pre-built OS's
  * can then enter ssh as root using our ssh keys
  * currently supports fedora and ubuntu
* there is also support for dealing with the BIOS config, i.e. to schedule, prior to rebooting
  * a complete reset of the BIOS settings
  * and then specific changes

## a sample session

run this on `sopnode-l1`

```bash
# the plain command name is liveboot
# but there is a convenience alias defined for you
type lb
lb is aliased to `liveboot'
```

### `status`

probe a node for things like:
* power state,
* selected meaningful BIOS Settings,
* virtual media attachments,
* and does it answer ICMP or TCP/22

```bash
sopnode-l1 /usr/share/sopnode-liveboot (main $=) #
lb status w3
---------- status of sopnode-w3.inria.fr - iDRAC Liveboot sopnode-w3-drac.inria.fr
  power state: Off
   SysProfile: PerfPerWattOptimizedDapc
  ProcCStates: Enabled
Vmedia slot 1: http://138.96.245.50:80/bootable-images/f37-sopnode-liveboot.iso
Vmedia slot 2: http://138.96.245.50:80/bootable-images/cidata-seed-w3.iso
         PING: KO
          SSH: KO
```

### `liveboot`

this of course is the main purpose; assume you want to reboot sopnode-w3 under ubuntu-18

```bash
# this will return only when the reboot has completed
lb liveboot w3 -i u18
```

to see the list of available images, for now just do

```bash
ls /srv/shares/bootable-images/
```

where the short names like `u18` above are symlinks to real images

see below about how to produce these images

### `wait`

this is to wait for a node to be ssh-reachable

**note** at this early stage, the cloud-init config has a hard-wired set of authorized keys:

* the sopnode servers themselves (i.e. the root user)
* TT+DS+TP

```bash
lb wait w3 && echo w3 is ssh-ready
```

### `diskboot`

to reboot the node under its "normal" OS - i.e. the one on its hard drive, do this

```bash
lb diskboot w3
```

### `biosget` : inspecting the BIOS settings

you can see them all

```
lb biosget w3
BIOS settings captured on sopnode-w3-drac.inria.fr on 2023 03 06 @ 17:44:37
                  AcPwrRcvry: Last
             AcPwrRcvryDelay: Immediate
<snip>
             WorkloadProfile: NotAvailable
                  WriteCache: Disabled
                WriteDataCrc: Disabled
```

or provide a pattern to restrict the output

```
lb biosget w3 profile
BIOS settings captured on sopnode-w3-drac.inria.fr on 2023 03 06 @ 17:46:02 with pattern=`profile`
     SysProfile: PerfPerWattOptimizedDapc
WorkloadProfile: NotAvailable

lb biosget w3 'profile|usb'
BIOS settings captured on sopnode-w3-drac.inria.fr on 2023 03 06 @ 17:46:10 with pattern=`profile|usb`
ControlledTurboMinusBin: 0
         GenericUsbBoot: Disabled
            InternalUsb: On
             SysProfile: PerfPerWattOptimizedDapc
         UsbManagedPort: On
               UsbPorts: AllOn
        WorkloadProfile: NotAvailable
```

### simpler power management

```bash
# turn on, reboot, turn off
lb on w3
lb reboot w3
lb off w3
```

### other features

there are other features implemented, oriented towards:

* resetting the BIOS
* changing BIOS settings
* as a corollary, inspecting the job queue in the DRAC  
  be aware that when you change a bios setting, it's not applied immediately (it
  makes sense) but kept in a job queue

all this is maybe not quite entirely smooth at this point,
so please start with using the simple features above

### devel / tmp notes

there's a need to better understand the logic of how the drac and the BIOS are
supposed to interact; see also

<https://github.com/dell/iDRAC-Redfish-Scripting/issues/249>

**WARNING**

if you do try to mess with the BIOS settings this way,
and you hit a wall: trying to insert a virtual media complains about the server
not having 1GB of RAM (sic): then do a biosreset, and reboot as many times as needed

## strategy

### one-time

* build a `cloud-init` capable live image for the target distribution
  * fedora: use `livecd-creator`
  * ubuntu: use the upstream public image and tweak its grub config
    **note** in theory there are other means to achieve that; in particular
    https://help.ubuntu.com/community/LiveCDCustomization, even if my first
    attempts seemed unrewarding, maybe this could use another look

### each session

* build a cloud-init config that contains our ssh keys (will depend on the slice)
* expose these 2 ISOs using redfish virtual media, and boot from there
* the HHD-installed OS (here fedora37) is totally untouched, so it can still be used if
  needed (see `diskboot`)

### diskless ?

* in a first step, keep the live session totally diskless
* later on we can consider shrinking the disk exposed
  to the current fedora installation, so that the live session
  can store stuff on the disk and thus have more memory space

## building images

```{warning}
this is still WIP
```

### ubuntu liveboot

we patch the standard ubuntu image, e.g.

```shell
# from https://releases.ubuntu.com/22.04/ubuntu-22.04.2-live-server-amd64.iso
-rw-r--r-- 1 root root 1474873344 Feb 16 15:41 ubuntu-22.04.1-live-server-amd64.iso
```

using our home-brewed tool like so

```shell
./patch-ubuntu-image.sh /srv/shares/bootable-images/public/ubuntu-22.04.2-live-server-amd64.iso
```

#### of interest for troubleshooting

* use Alt-F2 to get a login shell without the password
* https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html
* https://cloudinit.readthedocs.io/en/latest/howto/bugs.html#collect-logs

#### status

* 22: OK
* 20: kind of OK
  + the console is stuck at 'select your language' (harmless)
  + **HOWEVER** when rebooting the system enters an endless loop of squashfs error
* 18: OK as well

#### epilogue: `livefs-editor` ?

should we switch to using livefs-editor

see also https://github.com/mwhudson/livefs-editor/issues/31

### fedora liveboot

here's what we need:

https://docs.fedoraproject.org/en-US/quick-docs/creating-and-using-a-live-installation-image/#proc_creating-and-using-live-cd

here again, working from sopnode-l1

#### prerequisites

```shell
dnf install livecd-tools fedora-kickstarts pykickstart
```

#### f37

inspired from <https://www.spinics.net/linux/fedora/fedora-users/msg516742.html>

```bash
cd fedora
build-rpm.sh f37
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

#### status

* works with rawhide
* scripting for fedora37
* need to check alterative versions as well ?

### rocky liveboot

very close to fedora, so the code is also in the `fedora/` folder

* kickstart files can be found here
  https://github.com/rocky-linux/kickstarts/tree/r9
  

### cloud-init images

based on <https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html#creating-a-disk>

```shell
# create an ISO image suitable for cloud-init
seed-cloud-init.sh /srv/shares/bootable-images/cidata-seed.iso cloud-init-template.yaml
```

## issues

please use https://github.com/sopnode/liveboot/issues
