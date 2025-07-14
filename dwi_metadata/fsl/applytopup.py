#!/usr/bin/python3

from os import path as op
import subprocess
from tqdm import tqdm
import numpy

from dwi_metadata import ACQUISITIONS


def run(dicomdir, topupdir, applytopupdir, strides):

    mrconvert_cmd = ['mrconvert',
                      '-quiet',
                      '-coord', '3', '0',
                      '-axes', '0,1,2',
                      #'-config', 'RealignTransform', 'true', # Shouldn't matter
                      '-strides', ','.join(map(str, strides[0:3]))]

    applytopup_image_list = []
    for acq in tqdm(ACQUISITIONS,
                    desc='Running applytopup on individual volumes',
                    leave=False):
        temp_image_path = op.join(applytopupdir, f'{acq}.nii')
        temp_eddycfg_path = op.join(applytopupdir, f'{acq}.cfg')
        temp_eddyidx_path = op.join(applytopupdir, f'{acq}.idx')
        subprocess.run(mrconvert_cmd
                       + [op.join(dicomdir, f'{acq}'),
                          temp_image_path,
                          '-export_pe_eddy', temp_eddycfg_path, temp_eddyidx_path],
                       check=True)
        # While applytopup will run on images that claim to have phase encoding along the third axis,
        #   it will have no effect on the image data
        eddycfg_data = numpy.loadtxt(temp_eddycfg_path)
        if eddycfg_data[2] != 0:
            continue
        applytopup_image_path = op.join(applytopupdir, f'{acq}_applytopup.nii.gz')
        subprocess.run(['applytopup',
                        f'--imain={temp_image_path}',
                        f'--datain={temp_eddycfg_path}',
                        '--inindex=1',
                        f'--topup={op.join(topupdir, "out")}',
                        f'--out={applytopup_image_path}',
                        '--method=jac'],
                       check=True)
        applytopup_image_list.append(applytopup_image_path)

    subprocess.run(['mrcat',
                    '-quiet',
                    '-axis', '3',
                    '-config', 'RealignTransform', 'false']
                    + applytopup_image_list
                    + [op.join(applytopupdir, 'applytopup.mif')],
                   check=True)
