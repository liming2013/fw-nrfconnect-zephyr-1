#!/usr/bin/env python3
#
# Copyright (c) 2019 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-BSD-5-Clause-Nordic

import argparse
import yaml
import re
from os import path


def remove_item_not_in_list(list_to_remove_from, list_to_check):
    for x in list_to_remove_from:
        if x not in list_to_check and x != 'app':
            list_to_remove_from.remove(x)

def after_before(x_dict, to_check, after_before):
    return type(x_dict['placement']) == dict and \
                after_before in x_dict['placement'].keys() and \
                x_dict['placement'][after_before][0] == to_check


def resolve(reqs, flash_size):
    solution = list(['app'])

    [[remove_item_not_in_list(reqs[x]['placement'][before_after], reqs.keys())
      for x in reqs.keys() if type(reqs[x]['placement']) == dict
      and before_after in reqs[x]['placement'].keys()]
     for before_after in ['before', 'after']]

    unsolved = [x for x in reqs.keys() if type(reqs[x]['placement']) == dict and
                ('before' in reqs[x]['placement'].keys() or
                 'after' in reqs[x]['placement'].keys())]

    last = [x for x in reqs.keys() if type(reqs[x]['placement']) == str and reqs[x]['placement'] == 'last']
    if last:
        assert(len(last) == 1)
        solution.append(last[0])
        current = last[0]
        more_deps = True
        while more_deps:
            next = [x for x in reqs.keys() if after_before(reqs[x], current, 'before')]
            if next:
                solution.insert(solution.index(current), next[0])
                current = next[0]
                unsolved.remove(current)

            else:
                more_deps = False

    current = 'app'
    more_deps = True
    while more_deps:
        next = [x for x in reqs.keys() if after_before(reqs[x], current, 'before')]
        if next:
            assert(len(next) == 1)
            current = next[0]
            unsolved.remove(current)
            solution.insert(0, current)
        else:
            more_deps = False

    current = 'app'
    more_deps = len(unsolved) > 0
    while more_deps:
        next = [x for x in reqs.keys() if after_before(reqs[x], current, 'after')]
        if next:
            assert (len(next) == 1)
            current = next[0]
            unsolved.remove(current)
            solution.append(current)
        else:
            more_deps = False

    # First image starts at 0
    reqs[solution[0]]['address'] = 0
    for i in range(1, len(solution)):
        current = solution[i]
        previous = solution[i-1]
        if current == 'app':
            reqs['app'] = dict()
            reqs['app']['placement'] = ''
        if reqs[current]['placement'] == 'last':
            reqs[current]['address'] = flash_size - reqs[current]['size']
        else:
            if previous != 'app':
                reqs[current]['address'] = reqs[previous]['address'] + reqs[previous]['size']

    if solution.index('app') == len(solution) - 1:
        reqs['app']['size'] = flash_size - reqs['app']['address']  # App is at the back
    else:
        address_of_image_after_app = reqs[solution[solution.index('app') + 1]]['address']
        reqs['app']['size'] = address_of_image_after_app - reqs['app']['address']


def get_size_configs(configs):
    result = dict()
    for i in configs:
        for line in i.readlines():
            match = re.match(r'#define CONFIG_PARTITION_MANAGER_RESERVED_SPACE_(\w*) (0x[0-9a-fA-F]*)', line)
            if match:
                if int(match.group(2), 16) != 0:
                    result[match.group(1).lower()] = int(match.group(2), 16)
    return result


def load_size_config(adr_map, configs):
    size_configs = get_size_configs(configs)
    for k, v in adr_map.keys():
        if 'size' not in v.keys():
            adr_map[k]['size'] = size_configs[k]


def load_adr_map(adr_map, input_files, output_file_name):
    for f in input_files:
        img_conf = yaml.safe_load(f)
        img_conf[list(img_conf.keys())[0]]['out_path'] = path.join(path.dirname(f.name), output_file_name)
        adr_map.update(img_conf)


def generate_override(input_files, output_file_name, flash_size, configs, app_override_file):
    adr_map = dict()
    load_adr_map(adr_map, input_files, output_file_name)
    load_size_config(adr_map, configs)
    resolve(adr_map, flash_size)
    adr_map['app']['out_path'] = app_override_file
    for img, conf in adr_map.items():
        open(conf['out_path'], 'w').write('''\
#undef CONFIG_FLASH_BASE_ADDRESS
#define CONFIG_FLASH_BASE_ADDRESS %s''' % hex(conf['address']))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parse given input configurations and generate override header files.",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-i", "--input", type=argparse.FileType('r', encoding='UTF-8'), nargs="+",
                        help="List of JSON formatted config files. See tests in this file for examples.")
    parser.add_argument("-c", "--configs", type=argparse.FileType('r', encoding='UTF-8'), nargs="+",
                        help="List of paths to generated 'autoconf.h' files.")
    parser.add_argument("-s", "--flash-size", help="Size of flash of device.")
    parser.add_argument("-o", "--output", help="Output file name. Will be stored in same dir as input.")
    parser.add_argument("--app-override-file", help="Path to root app override.h file path.")

    args = parser.parse_args()

    return args


def test():
    test_0 = {
        'e': {'placement': {'before': ['app']}, 'size': 100},
        'a': {'placement': {'before': ['b']}, 'size': 100},
        'd': {'placement': {'before': ['e']}, 'size': 100},
        'c': {'placement': {'before': ['d']}, 'size': 100},
        'h': {'placement': 'last', 'size': 20},
        'f': {'placement': {'before': ['g']}, 'size': 20},
        'g': {'placement': {'before': ['h']}, 'size': 20},
        'b': {'placement': {'before': ['c']}, 'size': 20}}
    resolve(test_0, flash_size=1000)

    test_2 = {'mcuboot': {'placement': {'before': ['app', 'spu']}, 'size': 200},
              'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100}}
    resolve(test_2, flash_size=1000)

    test_3 = {'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100}}
    resolve(test_3, flash_size=1000)

    test_4 = {'spu': {'placement': {'before': ['app']}, 'size': 100},
              'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 200}}
    resolve(test_4, flash_size=1000)

    test_5 = {'provision': {'placement': 'last', 'size': 100},
              'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 100},
              'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 50},
              'spu': {'placement': {'before': ['app']}, 'size': 100}}
    resolve(test_5, flash_size=1000)
    pass


def main():
    args = parse_args()

    if args.input is not None:
        generate_override(args.input, args.output, args.flash_size, args.configs, args.app_override_file)
    else:
        print("No input, running tests.")
        test()


if __name__ == "__main__":
    main()
