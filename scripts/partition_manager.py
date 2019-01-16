#!/usr/bin/env python3
#
# Copyright (c) 2019 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-BSD-5-Clause-Nordic

import argparse
import yaml
import re
from os import path


def before(adr_map, dep, img):
    return hex(int(adr_map[dep]['address'], 16) - int(adr_map[img]['size'], 16))


def after(adr_map, dep):
    return hex(int(adr_map[dep]['address'], 16) + int(adr_map[dep]['size'], 16))


# Fill out non-trivial addresses
def resolve_dependincies(adr_map, to_check=None):
    for img in adr_map.keys():
        if to_check and img != to_check:
            continue
        address_config = adr_map[img]['address']
        if type(address_config) == int:
            continue
        elif address_config.startswith('before') or address_config.startswith('after'):
            dep = address_config.split(' ')[1]
            # Invoke recursively to ensure all dependencies resolved
            resolve_dependincies(adr_map, dep)
            if 'before' in address_config:
                address = before(adr_map, dep, img)
            else:
                address = after(adr_map, dep)

            adr_map[img]['address'] = address
        elif 'if' in address_config:
            match = re.match(r'if (\w*) ([\w ]*) else ([\w ]*)', address_config)
            adr_map[img]['address'] = match.group(2) if match.group(1) in adr_map.keys() else match.group(3)
            resolve_dependincies(adr_map, img)  # Need to re-call to ensure resolution


def generate_override(input_files, output_file_name):
    adr_map = dict()
    for f in input_files:
        img_conf = yaml.safe_load(f)
        img_conf[list(img_conf.keys())[0]]['out_path'] = path.join(path.dirname(f.name), output_file_name)
        adr_map.update(img_conf)

    resolve_dependincies(adr_map)

    # TODO check for collisions

    for img, conf in adr_map.items():
        open(conf['out_path'], 'w').write('''\
#undef CONFIG_FLASH_BASE_ADDRESS
#define CONFIG_FLASH_BASE_ADDRESS %s''' % conf['address'])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parse given input configurations and generate override header files.",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-i", "--input", type=argparse.FileType('r', encoding='UTF-8'), nargs="+",
                        help="List of JSON formatted config files. See tests in this file for examples.")
    parser.add_argument("-o", "--output", help="Output file name. Will be stored in same dir as input.")
    args = parser.parse_args()

    return args


def test():
    test_0 = {'a': {'address': 'after b', 'size': '0x10'},
              'b': {'address': 'after c', 'size': '0x1000'},
              'c': {'address': '0', 'size': '0x1000'},
              'd': {'address': 'before e', 'size': '0x1000'},
              'e': {'address': '0xF000', 'size': '0x1000'}}
    resolve_dependincies(test_0)
    assert (test_0['a']['address'] == '0x2000')
    assert (test_0['d']['address'] == '0xe000')

    test_1 = {'a': {'address': 'if c after b else before b', 'size': '0x2000'},
              'b': {'address': 'after c', 'size': '0x4000'},
              'c': {'address': 'if d 0x1000 else 0', 'size': '0x4000'},
              'd': {'address': '0x7000', 'size': '0x100'}}
    resolve_dependincies(test_1)
    assert (test_1['a']['address'] == '0x9000')


def main():
    args = parse_args()

    if args.input is not None:
        generate_override(args.input, args.output)
    else:
        print("No input, running tests.")
        test()


if __name__ == "__main__":
    main()
