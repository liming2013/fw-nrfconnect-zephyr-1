#!/usr/bin/env python3
#
# Copyright (c) 2019 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: LicenseRef-BSD-5-Clause-Nordic

import argparse
import yaml
import re
from os import path


def valid_solution(reqs, solution):
    for img in reqs.keys():
        current_idx = solution.index(img)
        placement = reqs[img]['placement']
        if type(placement) == dict:
            if 'before' in placement.keys():
                expected_idx = min([solution.index(x) for x in placement['before'] if x in solution]) - 1
            elif 'after' in placement.keys():
                expected_idx = max([solution.index(x) for x in placement['before'] if x in solution]) + 1
            else:
                raise RuntimeError("Invalid placement config: " + str(list(placement.keys())))
            if expected_idx == -1:
                return False
        else:
            if placement == 'last':
                expected_idx = len(solution) - 1
            elif placement == 'first':
                expected_idx = 0
            else:
                raise RuntimeError("Invalid placement config: " + placement)
        if expected_idx != current_idx:
            return False
    return True


def remove_item_not_in_list(list_to_remove_from, list_to_check):
    for x in list_to_remove_from:
        if x not in list_to_check:
            list_to_remove_from.remove(x)


def resolve(reqs, flash_size, size_configs):
    solution = list(reqs.keys())
    solution.append('app')

    # TODO check for conflicting configurations, where more than one image wants in front or behind the same image
    while not valid_solution(reqs, solution):
        for img in reqs.keys():
            placement = reqs[img]['placement']
            if type(placement) == dict:
                if 'before' in placement.keys():
                    remove_item_not_in_list(placement['before'], solution)
                    idx = solution.index(placement['before'][0]) - 1
                elif 'after' in placement.keys():
                    remove_item_not_in_list(placement['after'], solution)
                    idx = solution.index(placement['after'][0]) + 1
                else:
                    raise RuntimeError("Invalid placement config: " + str(list(placement.keys())))
                if idx == -1:
                    idx = 0
            else:
                if placement == 'last':
                    idx = -1
                elif placement == 'first':
                    idx = 0
                else:
                    raise RuntimeError("Invalid placement config: " + placement)

            solution[solution.index(img)], solution[idx] = solution[idx], solution[solution.index(img)]

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
            if 'size' not in reqs[solution[i-1]].keys():
                reqs[previous]['size'] = size_configs[previous]
            reqs[current]['address'] = reqs[previous]['address'] + reqs[previous]['size']


def get_size_configs(configs):
    result = dict()
    for i in configs:
        for line in i.readlines():
            match = re.match(r'#define CONFIG_PARTITION_MANAGER_RESERVED_SPACE_(\w*) (0x[0-9a-fA-F]*)', line)
            if match:
                if int(match.group(2), 16) != 0:
                    result[match.group(1).lower()] = int(match.group(2), 16)
    return result


def generate_override(input_files, output_file_name, flash_size, configs, app_override_file):
    size_configs = get_size_configs(configs)
    print(size_configs)
    adr_map = dict()
    for f in input_files:
        img_conf = yaml.safe_load(f)
        img_conf[list(img_conf.keys())[0]]['out_path'] = path.join(path.dirname(f.name), output_file_name)
        adr_map.update(img_conf)

    resolve(adr_map, flash_size, size_configs)

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
    parser.add_argument("-s", "--flash-size", default=100000, help="Size of flash of device.")
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
        'b': {'placement': {'before': ['c']}, 'size': 200}}
    resolve(test_0)

    test_2 = {'mcuboot': {'placement': {'before': ['app', 'spu']}, 'size': 200},
              'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100}}
    resolve(test_2)

    test_3 = {'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100}}
    resolve(test_3)

    test_4 = {'spu': {'placement': {'before': ['app']}, 'size': 100},
              'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 200}}
    resolve(test_4)

    test_5 = {'provision': {'placement': 'last', 'size': 100},
              'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 100},
              'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 1000},
              'spu': {'placement': {'before': ['app']}, 'size': 100}}
    resolve(test_5)


def main():
    args = parse_args()

    if args.input is not None:
        generate_override(args.input, args.output, args.flash_size, args.configs, args.app_override_file)
    else:
        print("No input, running tests.")
        test()


if __name__ == "__main__":
    main()
