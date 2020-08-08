import argparse
from dataclasses import dataclass
import urllib.request
import zipfile
import os
import shutil
import subprocess
import csv
import io

''' Script to run blender benchmarks. It will download files the first time 
    run with python3 run_benchmark.py PATH_TO_BLENDER_EXE OUT_CSV.csv
    use --help for options
'''


@dataclass
class Test:
    ''' Handles getting data and running test '''
    name: str
    archive_url: str
    blend_file: str
    frame_num: int
    settings: dict  # settings to set before running file
    command_options: list

    def get_archive(self):
        if os.path.exists(self.name):
            print('Archive', self.name, 'Exists already')
        else:
            print('Getting archive', self.name, self.archive_url)
            urllib.request.urlretrieve(self.archive_url, "archive.zip")
            with zipfile.ZipFile("archive.zip", 'r') as zip_ref:
                zip_ref.extractall(os.path.join('scenes', self.name))
            print('Extracted to', self.name)
            os.remove("archive.zip")

    def run_test(self, blender_exe, render_backend, device_options=[]):
        blend_file = os.path.join('scenes', self.name, self.blend_file)
        renderer = render_backend if render_backend == 'RPR' else 'CYCLES'
        set_backend = None
        if renderer == 'CYCLES':
            set_backend = f"import bpy; bpy.context.preferences.addons['CYCLES'].preferences.compute_device_type = {render_backend}"

        cmd = [blender_exe, '-b', blend_file, '-E', 'CYCLES', '-f', str(self.frame_num)] 
        if set_backend:
            cmd += ['--python-expr', set_backend]
        cmd += self.command_options
        print('Running', cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # parse stdout
        time = ''
        max_mem = ''
        started, ended = False, False

        for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
            tokens = line.split('|')
            if not len(tokens) > 1:
                continue

            if started and "Time:" in tokens[1]:
                time = tokens[1].split('Time:')[1]

            if not started and 'Remaining' in tokens[2]:
                started = True
            elif started and not ended and 'Remaining' not in tokens[2]:
                ended = True
                max_mem = tokens[2].split(':')[2]
        print('Done rendering', self.blend_file)
        return {'Test Name':self.name,
                'Render Time': time,
                'Peak Memory': max_mem}


# rendering backends
ACCEPTED_BACKENDS = ('OPENCL', 'CPU', 'RPR', 'OPTIX', 'CUDA')


# list of tests to do
TESTS = [
    Test('BMW', 'https://download.blender.org/demo/test/BMW27_2.blend.zip', 'bmw27/bmw27_gpu.blend', 1, {}, []),
]


RESULT_COLUMNS = ['Test Name', 'Render Time', 'Peak Memory']

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('blender_exe', help="Path to blender executable")
    parser.add_argument('-backend', metavar='-b', default='OpenCL', choices=ACCEPTED_BACKENDS, help="Rendering backend to use, choices " + str(ACCEPTED_BACKENDS))
    parser.add_argument('-gpu_statees', metavar='-gpus', default='1', help='Comma separated list of devices to use.  CPU is 0')
    parser.add_argument('output', help='Output CSV file')
    args = parser.parse_args()

    with open(args.output, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for test in TESTS:
            test.get_archive()
            writer.writerow(test.run_test(args.blender_exe, args.backend))