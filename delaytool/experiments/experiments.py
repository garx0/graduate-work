import os, sys, subprocess

x_ext = ".exe" if sys.platform.startswith("win") else ""
delaytool_path = "../cmake-build-debug/delaytool" + x_ext

# split into directory, name and extension
def fullsplit(path):
    import os
    splitext = os.path.splitext(path)
    return (*os.path.split(splitext[0]), splitext[1])

def get_bw_stats(filename_in, size_factor=1.0):
    filename_out = "temp.xml"
    command = f"{delaytool_path} {filename_in} {filename_out} -s mock -f {size_factor}"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    bw_min, bw_max, bw_mean, bw_var = 0, 0, 0, 0
    for line_enc in process.communicate():
        lines = line_enc.decode('utf-8')
        for line in lines.split('\n'):
            if line.startswith('bwUsage'):
                tokens = line.replace('=', ',').split(',')
                numbers = []
                for token in tokens:
                    try:
                        num = float(token)
                        numbers.append(num)
                    except ValueError:
                        pass
                if(len(numbers) >= 4):
                    bw_min, bw_max, bw_mean, bw_var = numbers[:4]
                    break
    if os.path.isfile(filename_out):
        os.remove(filename_out)
    return bw_min, bw_max, bw_mean, bw_var


def get_rate(filename_in):
    import xml.etree.ElementTree as etree
    tree = etree.parse(filename_in)
    root = tree.getroot()
    return int(root.find('resources').find('link').get('capacity'))

# bw is expected average (if by_max = False) or maximum (if by_max = True) bandwidth
# voq_dur is duration of voq processing period in ms
# returns calculation time in seconds (float)
def calc_delays(filename_in, filename_out, bw_stats, scheme, bw, by_max=False, cell_size=None, voq_l=None, jitdef=0):
    from math import ceil, inf
    from datetime import datetime
    bw_min, bw_max, bw_mean, bw_var = bw_stats
    bw_anchor = bw_max if by_max else bw_mean
    size_factor = bw / bw_anchor
    new_bw_max = bw_max * size_factor
    if new_bw_max > 1:
        print(f"max bandwidth will be: {new_bw_max} > 1, try smaller avg bandwidth")
        return 0, 'bw overload'
    command = f"{delaytool_path} {filename_in} {filename_out} -s {scheme} -f {size_factor} --bpmaxit 0"
    if jitdef is not None:
        command += f" --jitdef {jitdef}"
    if scheme in ("oqa", "oqb", "voqa", "voqb"):
        if cell_size is None:
            print("error, specify cell size")
            return 0, 'py_arg'
        command += f" -c {cell_size}"
    if scheme in ("voqa", "voqb"):
        if voq_l is None:
            print("error, specify voq processing period length in cells")
            return 0, 'py_arg'
        command += f" -p {voq_l}"
    print(command)
    t1 = datetime.now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    err_msg = None
    err = None
    try:
        for line_enc in process.communicate():
            lines = line_enc.decode('utf-8')
            print(lines)
            for line in lines.split('\n'):
                if line.lower().startswith("error"):
                    err_msg = line
                    err = 'other'
    except KeyboardInterrupt:
        err_msg = 'cancelled this command execution'
        err = 'cancel'
    t2 = datetime.now()
    if err_msg is not None:
        print(err_msg)
        return 0, err
    return (t2-t1).total_seconds(), err

def size_stats(filename_in):
    import xml.etree.ElementTree as etree
    tree = etree.parse(filename_in)
    root = tree.getroot()
    vls = root.find('virtualLinks')
    smax_list = []
    for vl in vls.findall('virtualLink'):
        smax_list.append(int(vl.get('lmax')))
    smax_max = max(smax_list)
    smax_mean = sum(smax_list) / len(smax_list)
    return smax_max, smax_mean

def delay_stats(filename_in):
    import xml.etree.ElementTree as etree
    tree = etree.parse(filename_in)
    root = tree.getroot()
    vls = root.find('virtualLinks')
    delays = []
    jitters = []
    for vl in vls.findall('virtualLink'):
        paths_delay = []
        paths_jit = []
        for path_el in vl.findall('path'):
            if path_el.get('maxDelay') is None:
                return 0, 0, 0, 0
            paths_delay.append(int(path_el.get('maxDelay')))
            paths_jit.append(int(path_el.get('maxJit')))
        delays.append(sum(paths_delay) / len(paths_delay))
        jitters.append(sum(paths_jit) / len(paths_jit))
    delays_max = max(delays)
    jitters_max = max(jitters)
    delays_mean = sum(delays) / len(delays)
    jitters_mean = sum(jitters) / len(jitters)
    return delays_max, jitters_max, delays_mean, jitters_mean

def get_n_vlinks(filename_in):
    import xml.etree.ElementTree as etree
    tree = etree.parse(filename_in)
    root = tree.getroot()
    vls = root.find('virtualLinks')
    return len(vls.findall('virtualLink'))

# experimemts on one file with VL config : filename_in
# file_out is file object, not filename (csv table).
# function writes lines to the file without writing header.
def exp_config(filename_in, file_out, scheme_list, cell_size, voq_dur_list,
    bw_list, n_iter, jitdef=None, by_max=False):
    from math import ceil
    split = fullsplit(filename_in)
    delays_dir = os.path.join(split[0], "delays")
    if not os.path.exists(delays_dir):
        os.makedirs(delays_dir)
    bw_stats = get_bw_stats(filename_in)
    bw_anchor = bw_stats[1] if by_max else bw_stats[2]
    rate = get_rate(filename_in)
    n_vl = get_n_vlinks(filename_in)
    for scheme in scheme_list:
        vd_list_end = 1
        is_cell = scheme in ("oqa", "oqb", "voqa", "voqb")
        is_voq = scheme in ("voqa", "voqb")
        if is_voq:
            vd_list_end = None
        for voq_dur in voq_dur_list[:vd_list_end]:
            voq_l = ceil(voq_dur * rate / cell_size)
            voq_dur_real = voq_l * cell_size / rate
            for bw in bw_list:
                size_factor = bw / bw_anchor
                filename_config = f"{os.path.join(delays_dir, split[1])}_delays_{scheme}"
                if is_cell:
                    filename_config += f"_c={cell_size}"
                if is_voq:
                    filename_config += f"_lt={voq_dur}"
                filename_config += f"_bw{'max' if by_max else 'avg'}={bw}{split[2]}"
                avg_time = 0
                for it in range(n_iter):
                    t, err = calc_delays(filename_in, filename_config, bw_stats,
                        scheme, bw, by_max, cell_size, voq_l, jitdef)
                    if err is not None:
                        avg_time = 0
                        break
                    print(f"calc time: {t} s")
                    avg_time += t
                avg_time /= n_iter
                if avg_time != 0:
                    delays_max, jitters_max, delays_mean, jitters_mean = delay_stats(filename_config)
                    smax_max, smax_mean = size_stats(filename_config)
                else:
                    delays_max, jitters_max, delays_mean, jitters_mean, smax_max, smax_mean = 0, 0, 0, 0, 0, 0

                print(f'smax_max = {smax_max}, smax_mean = {smax_mean}')
                config_name = split[1]
                new_bw_stats = get_bw_stats(filename_in, size_factor)
                if err is None:
                    err = ""
                file_out.write(f'"{config_name}",{n_vl},{scheme},{cell_size},{voq_dur},{voq_l},{voq_dur_real},'
                    + f'{bw},{jitdef},{delays_max},{delays_mean},{jitters_max},{jitters_mean},{avg_time},{rate},'
                    + f'{size_factor},{smax_max},{smax_mean},{new_bw_stats[0]},{new_bw_stats[1]},'
                    + f'{new_bw_stats[2]},{new_bw_stats[3]},{bw_stats[0]},{bw_stats[1]},'
                    + f'{bw_stats[2]},{bw_stats[3]},"{err}"\n')

# example:
# python experiments.py file1 file2 file3 file0
#     -s oqp voqa voqb oqa oqb -c 53 -d 128 256 -b 0.01 0.05 0.10 0.15 0.20 0.25 0.3 0.4 0.5 0.75
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', type=str, nargs='+')
    parser.add_argument('output_file', type=str)
    parser.add_argument('-s', '--scheme', type=str, nargs='+', dest='scheme',
        choices=["oqp", "voqa", "voqb", "oqa", "oqb", "mock"])
    parser.add_argument('-c', '--cellsize', type=int, dest='cell_size')
    parser.add_argument('-d', '--voqdur', type=float, nargs='+', dest='voq_dur',
        help="voq processing period duration in ms")
    parser.add_argument('-b', '--bw', type=float, nargs='+', dest='bw',
        help="average (or maximum if --max is present) usage of link bandwidth ratio in [0,1]")
    parser.add_argument('-i', '--iter', type=int, dest='n_iter', default=3,
        help="number of launches of one command to count average calculating time")
    parser.add_argument('-m', '--max', dest='by_max', action='store_true', help=
"by_max: if present, --bw arguments are values of max usage of link bandwidth, else they are values of average usage")
    parser.add_argument('-j', '--jitdef', dest='jitdef', help="set start jitters for all VL to specified value")

    args = parser.parse_args()
    filenames_in = args.input_file
    filename_out = args.output_file
    scheme_list = args.scheme
    cell_size = args.cell_size
    voq_dur_list = args.voq_dur
    bw_list = args.bw
    n_iter = args.n_iter
    by_max = args.by_max
    jitdef = args.jitdef

    with open(filename_out, "w") as file_out:
        # csv header
        file_out.write('config,n_vlinks,scheme,cell_size,voq_dur_spec,voq_length,voq_dur,'
            + 'bw,jitdef,delays_max,delays_mean,jitters_max,jitters_mean,time,rate,'
            + 'size_factor,smax_max,smax_mean,bw_min,bw_max,'
            + 'bw_mean,bw_var,bw_min_orig,bw_max_orig,'
            + 'bw_mean_orig,bw_var_orig,error\n')
        for filename_in in filenames_in:
            exp_config(filename_in, file_out, scheme_list, cell_size,
                voq_dur_list, bw_list, n_iter, jitdef, by_max)

if __name__ == "__main__":
    main()
