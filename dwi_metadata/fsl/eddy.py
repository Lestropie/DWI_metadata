#!/usr/bin/python3

import os
from os import path as op
import subprocess
from tqdm import tqdm

from dwi_metadata import ACQUISITIONS


def run(dicomdir, topupdir, eddydir, mask_path, strides):

    mrconvert_cmd = ['mrconvert',
                     '-quiet',
                     '-config', 'RealignTransform', 'true',
                     '-strides', ','.join(map(str, strides))]

    mrcat_image_list = []

    # TODO Concatenating all volumes for all acquisitions takes way too long for eddy to process
    # Want to derive a set of mrconvert calls that will extract just the first b=0
    #   and a small number of DWIs from each acquisition such that the net DWI coverage
    #   is reasonable but the total number of volumes processed is smaller
    # DWI table of acquisition is:
    #   - 1 x b=0
    #   - 12 x b=1500
    #   - 1 x b=0
    #   - 13 x b=1500
    #   - 1 x b=0
    # Across the set of acquisitions to use
    #   (16 or 24 depending on whether phase encoding along the third axis is permitted),
    #   pull the lead b=0 and then one or more suitable DWIs
    #   such that each diffusion sensitisation direction appears only once

    # TODO Can eddy deal with volumes with phase encoding along the third axis?
    #for acq in tqdm([item for item in ACQUISITIONS if item.pedir not in ('HF', 'FH')],
    for acq in tqdm(ACQUISITIONS,
                    desc='Conforming DICOM series for concatenation for eddy',
                    leave=False):
        temp_image_path = op.join(eddydir, f'{acq}.mif')
        subprocess.run(mrconvert_cmd
                       + [op.join(dicomdir, f'{acq}'),
                          temp_image_path],
                       check=True)
        mrcat_image_list.append(temp_image_path)

    concat_image_path = op.join(eddydir, 'in.mif')
    subprocess.run(['mrcat',
                    '-quiet',
                    '-config', 'RealignTransform', 'false',
                    '-axis', '3']
                   + mrcat_image_list
                   + [concat_image_path],
                   check=True)

    eddy_in_image_path = op.join(eddydir, 'in.nii')
    eddy_config_path = op.join(eddydir, 'in.cfg')
    eddy_index_path = op.join(eddydir, 'in.idx')
    eddy_bvec_path = op.join(eddydir, 'in.bvec')
    eddy_bval_path = op.join(eddydir, 'in.bval')
    subprocess.run(['mrconvert',
                    '-quiet',
                    '-config', 'RealignTransform', 'false',
                    concat_image_path,
                    eddy_in_image_path,
                    '-export_pe_eddy', eddy_config_path, eddy_index_path,
                    '-export_grad_fsl', eddy_bvec_path, eddy_bval_path],
                   check=True)
    os.remove(concat_image_path)

    eddy_mask_path = op.join(eddydir, 'mask.nii')
    subprocess.run(['mrconvert',
                    '-quiet',
                    mask_path,
                    eddy_mask_path,
                    '-strides', ','.join(map(str, strides[0:3])),
                    '-datatype', 'uint8'],
                   check=True)

    subprocess.run(['eddy',
                    f'--imain={eddy_in_image_path}',
                    f'--mask={eddy_mask_path}',
                    f'--index={eddy_index_path}',
                    f'--acqp={eddy_config_path}',
                    f'--bvecs={eddy_bvec_path}',
                    f'--bvals={eddy_bval_path}',
                    '--mb=2',
                    f'--topup={op.join(topupdir, "out")}',
                    '--flm=linear',
                    #'--interp=linear', # Would be faster, but seems to crash
                    f'--out={op.join(eddydir, "out")}'],
                   check=True)
