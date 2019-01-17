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


def item_is_placed(d, item, after_or_before):
    assert(after_or_before in ['after', 'before'])
    return type(d['placement']) == dict and after_or_before in d['placement'].keys() and d['placement'][after_or_before][0] == item


def remove_irrelevant_requirements(reqs):
    [[remove_item_not_in_list(reqs[x]['placement'][before_after], reqs.keys())
      for x in reqs.keys() if type(reqs[x]['placement']) == dict
      and before_after in reqs[x]['placement'].keys()]
     for before_after in ['before', 'after']]


def get_images_which_needs_resolving(reqs):
    return [x for x in reqs.keys() if type(reqs[x]['placement']) == dict and ('before' in reqs[x]['placement'].keys() or
            'after' in reqs[x]['placement'].keys())]


def solve_direction(reqs, unsolved, solution, ab):
    assert(ab in ['after', 'before'])
    current = 'app'
    cont = len(unsolved) > 0
    while cont:
        depends = [x for x in reqs.keys() if item_is_placed(reqs[x], current, ab)]
        if depends:
            assert(len(depends) == 1)
            if ab == 'before':
                solution.insert(solution.index(current), depends[0])
            else:
                solution.insert(solution.index(current) + 1, depends[0])
            current = depends[0]
            unsolved.remove(current)
        else:
            cont = False


def solve_from_last(reqs, unsolved, solution):
    last = [x for x in reqs.keys() if type(reqs[x]['placement']) == str and reqs[x]['placement'] == 'last']
    if last:
        assert(len(last) == 1)
        solution.append(last[0])
        current = last[0]
        cont = True
        while cont:
            depends = [x for x in reqs.keys() if item_is_placed(reqs[x], current, after_or_before='before')]
            if depends:
                solution.insert(solution.index(current), depends[0])
                current = depends[0]
                unsolved.remove(current)
            else:
                cont = False


def resolve(reqs):
    solution = list(['app'])
    remove_irrelevant_requirements(reqs)
    unsolved = get_images_which_needs_resolving(reqs)

    solve_from_last(reqs, unsolved, solution)
    solve_direction(reqs, unsolved, solution, 'before')
    solve_direction(reqs, unsolved, solution, 'after')

    return solution


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
    for k, v in adr_map.items():
        if 'size' not in v.keys() and k != 'app':
            adr_map[k]['size'] = size_configs[k]


def load_adr_map(adr_map, input_files, output_file_name, app_override_file):
    for f in input_files:
        img_conf = yaml.safe_load(f)
        img_conf[list(img_conf.keys())[0]]['out_path'] = path.join(path.dirname(f.name), output_file_name)
        adr_map.update(img_conf)
    adr_map['app'] = dict()
    adr_map['app']['placement'] = ''
    adr_map['app']['out_path'] = app_override_file


def set_addresses(reqs, solution, flash_size):
    # First image starts at 0
    reqs[solution[0]]['address'] = 0
    for i in range(1, solution.index('app') + 1):
        current = solution[i]
        previous = solution[i - 1]
        reqs[current]['address'] = reqs[previous]['address'] + reqs[previous]['size']

    has_image_after_app = len(solution) > solution.index('app') + 1
    if has_image_after_app:
        reqs[solution[-1]]['address'] = flash_size - reqs[solution[-1]]['size']
        for i in range(len(solution) - 2, solution.index('app'), -1):
            current = solution[i]
            previous = solution[i + 1]
            reqs[current]['address'] = reqs[previous]['address'] - reqs[current]['size']
        reqs['app']['size'] = reqs[solution[solution.index('app') + 1]]['address'] - reqs['app']['address']
    else:
        reqs['app']['size'] = flash_size - reqs['app']['address']


def write_override_files(adr_map):
    for img, conf in adr_map.items():
        open(conf['out_path'], 'w').write('''\
#undef CONFIG_FLASH_BASE_ADDRESS
#define CONFIG_FLASH_BASE_ADDRESS %s
#undef CONFIG_FLASH_LOAD_SIZE
#define CONFIG_FLASH_LOAD_SIZE %s
''' % (hex(conf['address']), hex(conf['size'])))


def generate_override(input_files, output_file_name, flash_size, configs, app_override_file):
    adr_map = dict()
    load_adr_map(adr_map, input_files, output_file_name, app_override_file)
    load_size_config(adr_map, configs)
    solution = resolve(adr_map)
    set_addresses(adr_map, solution, flash_size)
    write_override_files(adr_map)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Parse given input configurations and generate override header files.",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-i", "--input", type=argparse.FileType('r', encoding='UTF-8'), nargs="+",
                        help="List of JSON formatted config files. See tests in this file for examples.")
    parser.add_argument("-c", "--configs", type=argparse.FileType('r', encoding='UTF-8'), nargs="+",
                        help="List of paths to generated 'autoconf.h' files.")
    parser.add_argument("-s", "--flash-size", type=int, help="Size of flash of device.")
    parser.add_argument("-o", "--output", help="Output file name. Will be stored in same dir as input.")
    parser.add_argument("--app-override-file", help="Path to root app override.h file path.")

    args = parser.parse_args()

    return args


def test():
    td = {
        'e': {'placement': {'before': ['app']}, 'size': 100},
        'a': {'placement': {'before': ['b']}, 'size': 100},
        'd': {'placement': {'before': ['e']}, 'size': 100},
        'c': {'placement': {'before': ['d']}, 'size': 100},
        'j': {'placement': 'last', 'size': 20},
        'i': {'placement': {'before': ['j']}, 'size': 20},
        'h': {'placement': {'before': ['i']}, 'size': 20},
        'f': {'placement': {'after': ['app']}, 'size': 20},
        'g': {'placement': {'after': ['f']}, 'size': 20},
        'b': {'placement': {'before': ['c']}, 'size': 20},
        'app': {'placement': ''}}
    s = resolve(td)
    set_addresses(td, s, 1000)

    td = {'mcuboot': {'placement': {'before': ['app', 'spu']}, 'size': 200},
          'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100},
          'app': {'placement': ''}}
    s = resolve(td)
    set_addresses(td, s, 1000)

    td = {'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 100}, 'app': {'placement': ''}}
    s = resolve(td)
    set_addresses(td, s, 1000)

    td = {'spu': {'placement': {'before': ['app']}, 'size': 100},
          'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 200},
          'app': {'placement': ''}}
    s = resolve(td)
    set_addresses(td, s, 1000)

    td = {'provision': {'placement': 'last', 'size': 100},
          'mcuboot': {'placement': {'before': ['spu', 'app']}, 'size': 100},
          'b0': {'placement': {'before': ['mcuboot', 'app']}, 'size': 50},
          'spu': {'placement': {'before': ['app']}, 'size': 100},
          'app': {'placement': ''}}
    s = resolve(td)
    set_addresses(td, s, 1000)
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
