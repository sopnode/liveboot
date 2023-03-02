import sys
from argparse import ArgumentParser
from functools import wraps
from pathlib import Path

import yaml

from .liveboot import LiveBoot


CONFIG_FILENAME = "/etc/liveboot/liveboot.yaml"


SUBCOMMANDS = []
def subcommand(fun):
    SUBCOMMANDS.append(fun.__name__)
    return fun

def locate_subcommand(subcommand, tail=None):
    varname = f"{subcommand}"
    if tail:
        varname += f"_{tail}"
    return globals().get(varname, None)


def make_liveboot(config, stem):
    node = config['nodes'][stem]
    return LiveBoot(node['drac'], node['drac-username'], node['drac-password'])



@subcommand
def bios(config, args):
    with make_liveboot(config, args.stem) as l:
        l.show_bios_attributes(
            pattern=args.pattern,
            filename=args.output,
            mode='a' if  args.append else 'w')

def bios_add_arguments(parser):
    parser.add_argument("-p", "--pattern", default="")
    parser.add_argument("-o", "--output", default="")
    parser.add_argument("-a", "--append", default=False,
                        action='store_true',
                        help="open output file in append mode")
    parser.add_argument("stem")



@subcommand
def status(config, args):
    with make_liveboot(config, args.stem) as l:
        print(f"status of iDRAC {l}")
        D = {}
        D['power state'] = l.get_power_state()
        bios = l.get_bios_attributes()
        for attribute in config['status']['bios']:
            D[attribute] = bios[attribute]
        margin = max(map(lambda k: len(k), D.keys()))
        for k, v in D.items():
            print(f"{k:>{margin}}: {v}")
        l.show_virtual_medias()
def status_add_arguments(parser):
    parser.add_argument("stem")



@subcommand
def liveboot(config, args):
    # xxx
    # forge url of image
    # check image can be found (either from local disk or through http)
    # redo cloud-init iso
    # do it
    with make_liveboot(config, args.stem) as l:
        pass

def liveboot_add_arguments(parser):
    parser.add_argument("-i", "--image", default="f37-sopnode.iso")
    parser.add_argument("stem")


def main():
    parser = ArgumentParser()
    parser.add_argument("--config", default=CONFIG_FILENAME,
                        help="use another config file")
    subparsers = parser.add_subparsers(help="subcommand help")
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

    if getattr(args, 'stem') and args.stem not in known_stems:
        print(f"stem should be among one of {' '.join(known_stems)}")
        sys.exit(1)

    return args.func(config, args)

if __name__ == '__main__':
    main()
