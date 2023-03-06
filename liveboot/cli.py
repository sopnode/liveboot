"""
sopnode: the CLI

for each subcommand:

* a function (e.g. status)
* and the declaration of the allowed parameters (e.g. status_add_arguments(parser))
"""

# pylint: disable=missing-function-docstring

import sys
import os
import time
import logging
from argparse import ArgumentParser
from importlib import resources

import requests
import yaml

from .idrac import Idrac
from .version import __version__ as liveboot_version


CONFIG_FILENAME = "/etc/sopnode/sopnodes.yaml"


logging.getLogger().setLevel(level=os.getenv('LOGLEVEL', 'INFO').upper())

SUBCOMMANDS = []
def subcommand(fun):
    SUBCOMMANDS.append(fun.__name__)
    return fun

def locate_subcommand(subcommand, tail=None):
    varname = f"{subcommand}"
    if tail:
        varname += f"_{tail}"
    return globals().get(varname, None)


def make_idrac(config, stem):
    node = config['nodes'][stem]
    return Idrac(node['drac'], node['drac-username'], node['drac-password'])



@subcommand
def status(config, args):
    hostname = config['nodes'][args.stem]['hostname']
    with make_idrac(config, args.stem) as idrac:
        print(f"{10*'-'} status of {hostname} - iDRAC {idrac}")
        D = {}
        D['power state'] = idrac.get_power_state()
        bios_settings = idrac.get_bios_attributes()
        for attribute in config['status']['bios']:
            D[attribute] = bios_settings[attribute]
        for media in idrac.get_virtual_medias():
            D.update(idrac.virtual_media_status(media))
        ping_reachable = os.system(f"ping -c 1 -w 1 {hostname} < /dev/null >& /dev/null") == 0
        D['PING'] = 'OK' if ping_reachable else 'KO'
        ssh_reachable = os.system(f"nc --wait 0.5 {hostname} 22 < /dev/null >& /dev/null") == 0
        D['SSH'] = 'OK' if ssh_reachable else 'KO'
        margin = max(map(len, D.keys()))
        for k, v in D.items():
            print(f"{k:>{margin}}: {v}")

def status_add_arguments(parser):
    parser.add_argument("stem")



@subcommand
def biosget(config, args):
    with make_idrac(config, args.stem) as idrac:
        idrac.show_bios_attributes(pattern=args.pattern)

def biosget_add_arguments(parser):
    parser.add_argument("stem")
    parser.add_argument("pattern", nargs="?")



@subcommand
def biosset(config, args):
    if not args.settings:
        print("no setting to implement - exiting")
        return 1
    new_values = {}
    for setting in args.settings:
        try:
            name, value = setting.split('=')
            new_values[name] = value
        except ValueError:
            print(f"incorrect setting {setting}")
            return 1

    with make_idrac(config, args.stem) as idrac:
        idrac.set_bios_attributes(new_values)

def biosset_add_arguments(parser):
    parser.add_argument("stem")
    parser.add_argument("settings", nargs='+',
                        help="should be of the form setting=value")



@subcommand
def biosreset(config, args):
    with make_idrac(config, args.stem) as idrac:
        idrac.bios_reset()

def biosreset_add_arguments(parser):
    parser.add_argument("stem")



@subcommand
def queueget(config, args):
    with make_idrac(config, args.stem) as idrac:
        idrac.show_queue(args.all)

def queueget_add_arguments(parser):
    parser.add_argument("-a", "--all", default=False, action='store_true',
                        help="by default, only incomplete jobs are shown")
    parser.add_argument("stem")


@subcommand
def queueclear(config, args):
    with make_idrac(config, args.stem) as idrac:
        idrac.clear_queue(args.job_id)

def queueclear_add_arguments(parser):
    parser.add_argument("-j", "--job-id", default=None)
    parser.add_argument("stem")


@subcommand
def diskboot(config, args):
    with make_idrac(config, args.stem) as l:
        l.eject_virtual_media(1)
        l.eject_virtual_media(2)
        l.reboot()

def diskboot_add_arguments(parser):
    parser.add_argument("stem")



@subcommand
def liveboot(config, args):
    images_config = config['images']
    proto = images_config.get('proto', 'http')
    ip = images_config.get('ip')
    port = images_config.get('port', 80)
    path = images_config.get('path')
    image = args.image
    url_prefix = f"{proto}://{ip}:{port}/{path}"
    url1 = f"{url_prefix}/{image}"

    # check image can be found
    if (code := (requests.head(url1).status_code)) // 100 != 2:
        logging.error(f"got HHTP code {code} with {url1}")
        logging.error(f"this image does not seem to exist")
        return 1

    stem = args.stem
    packaged_data = resources.files('cloud-init')
    # generate the cloud-init seed
    template = packaged_data / "cloud-init-template.yaml.j2"
    # xxx these should come from the slice
    # they are hard-wired for now
    keysfile = "/etc/sopnode/sopnode-keys.yaml"
    seed = f"cidata-seed-{stem}.iso"
    path_to_seed = f"{images_config['absolute-path']}/{seed}"
    command = f"seed-cloud-init.sh {stem} {keysfile} {template} {path_to_seed}"
    logging.info(f"running command {command}")
    if os.system(command) != 0:
        logging.error(f"could not generate cidata seed")
        return 1

    url2 = f"{url_prefix}/{seed}"

    with make_idrac(config, args.stem) as idrac:
        if not (
            idrac.insert_virtual_media(1, url1)
        and idrac.insert_virtual_media(2, url2)
        # ignore result
        and (idrac.show_virtual_medias() or True)
        and idrac.set_next_one_time_boot_virtual_media_device(1)):
            logging.error("liveboot emergency exit")
            return 1
        idrac.reboot()
    return 0

def liveboot_add_arguments(parser):
    parser.add_argument("-i", "--image", default="f37-sopnode-liveboot.iso")
    parser.add_argument("stem")



@subcommand
def off(config, args):
    with make_idrac(config, args.stem) as idrac:
        return 0 if idrac.off() else 1

def off_add_arguments(parser):
    # xxx do we need to change the 3 durations on the command line ?
    parser.add_argument("stem")

@subcommand
def on(config, args):
    with make_idrac(config, args.stem) as idrac:
        return 0 if idrac.on() else 1

def on_add_arguments(parser):
    parser.add_argument("stem")

@subcommand
def reboot(config, args):
    with make_idrac(config, args.stem) as idrac:
        if not idrac.off():
            logging.error("cannot turn off")
            return 1
        return 0 if idrac.on() else 1

def reboot_add_arguments(parser):
    parser.add_argument("stem")



@subcommand
def wait(config, args):
    needs_newline = False
    hostname = config['nodes'][args.stem]['hostname']
    while True:
        if os.system(f"nc --wait 0.5 {hostname} 22 < /dev/null >& /dev/null") == 0:
            break
        time.sleep(args.period)
        if not args.silent:
            print('.', end="", flush=True)
            needs_newline = True
    if needs_newline:
        print()
    return 0

def wait_add_arguments(parser):
    parser.add_argument("-s", "--silent", default=False, action='store_true',
                        help="do not display dots as attempts are made")
    parser.add_argument("-p", "--period", default=3)
    parser.add_argument("stem")




@subcommand
def version(config, args):
    print(f"sopnode v{liveboot_version}")



def main() -> int:

    parser = ArgumentParser()
    parser.add_argument("--config", default=CONFIG_FILENAME,
                        help="use another config file")
    subparsers = parser.add_subparsers(help="subcommand help")
    # add all the subcommands subparsers
    for subcommand in SUBCOMMANDS:
        subparser = subparsers.add_parser(subcommand)
        subparser.set_defaults(func=locate_subcommand(subcommand))
        # locate e.g. bios_add_arguments
        add_arguments = locate_subcommand(subcommand, 'add_arguments')
        if add_arguments:
            add_arguments(subparser)


    args = parser.parse_args()

    try:
        with open(args.config) as feed:
            config = yaml.safe_load(feed)
            known_stems = list(config['nodes'].keys())
    except IOError as exc:
        print(f"could not load config file {args.config}, {exc}")
        sys.exit(1)

    if not getattr(args, 'func', None):
        parser.print_help()
        return 1

    if getattr(args, 'stem', None) and args.stem not in known_stems:
        print(f"stem should be among one of {' '.join(known_stems)}")
        sys.exit(1)

    return args.func(config, args)

if __name__ == '__main__':
    main()
