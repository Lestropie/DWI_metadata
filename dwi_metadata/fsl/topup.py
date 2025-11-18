#!/usr/bin/python3

import os
from os import path as op
import subprocess
from tqdm import tqdm

from dwi_metadata import ACQUISITIONS

TOPUP_CONFIG_PATH = op.join(os.environ['FSLDIR'], 'etc', 'flirtsch', 'b02b0_2.cnf')


def run(indir, localdir, strides):

    # Sensible concatenation of these images can't occur
    #   unless the transforms are realigned first
    mrconvert_cmd = ['mrconvert',
                      '-quiet',
                      '-coord', '3', '0',
                      '-axes', '0,1,2',
                      '-config', 'RealignTransform', 'true',
                      '-strides', ','.join(map(str, strides[0:3]))]

    image_paths = []
    for acq in tqdm(ACQUISITIONS,
                    desc='Extracting and converting first volume of each series',
                    leave=False):
        temp_image_path = op.join(localdir, f'{acq}.mif')
        subprocess.run(mrconvert_cmd +
                        [op.join(indir, f'{acq}'),
                        temp_image_path],
                       check=True)
        pe_dir = subprocess.run(['mrinfo',
                                 '-config', 'RealignTransform', 'false',
                                 temp_image_path,
                                 '-property', 'PhaseEncodingDirection'],
                                 capture_output=True).stdout
        if 'k' not in pe_dir.decode():
            image_paths.append(temp_image_path)

    concat_image_path_mif = op.join(localdir, 'all.mif')
    subprocess.run(['mrcat',
                    '-quiet',
                    '-axis', '3',
                    '-config', 'RealignTransform', 'false']
                   + image_paths
                   + [concat_image_path_mif],
                   check=True)

    concat_image_path_nii = op.join(localdir, 'in.nii')
    concat_petable_path = op.join(localdir, 'in.txt')
    subprocess.run(['mrconvert',
                    '-quiet',
                    '-config', 'RealignTransform', 'false',
                    concat_image_path_mif,
                    concat_image_path_nii,
                    '-export_pe_topup', concat_petable_path],
                   check=True)

    topup_out_prefix = op.join(localdir, 'out')
    topup_field_out = op.join(localdir, 'field.nii')
    topup_image_out = op.join(localdir, 'corr.nii')
    subprocess.run(['topup',
                    f'--imain={concat_image_path_nii}',
                    f'--datain={concat_petable_path}',
                    f'--out={topup_out_prefix}',
                    f'--fout={topup_field_out}',
                    f'--iout={topup_image_out}',
                    f'--config={TOPUP_CONFIG_PATH}'],
                   check=True)
