# 0.0.4 2023 May 17

* has support for building rocky images
  this is only partial for now though, as
  the resulting images have the impression that
  no rpm is installed (rpm -aq shows nothing)

# 0.0.3 2023 Mar 6

* exposed to pypi

# 0.0.2 2023 Mar 6

* support for the following subcommands
  status,
  biosget,biosset,biosreset,
  queueget,queueclear,
  diskboot,liveboot,
  off,on,reboot,
  wait,
  version

# 0.0.1 2023 Mar 4

* rudimentary commands: bios, status, liveboot
