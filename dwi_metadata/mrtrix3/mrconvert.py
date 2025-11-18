#!/usr/bin/python3

import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm

from .. import ACQUISITIONS
from .. import GradType
from .. import KeyvalueType
from .. import PEType

logger = logging.getLogger(__name__)



def run_dicom(indir, outdir, formats, reorient):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running MRtrix3 mrconvert from DICOM: '
                f'{formats.description}, reorient {reorient}')
    for acq in tqdm(ACQUISITIONS,
                  desc=f'Running MRtrix3 mrconvert: '
                       f'DICOM -> {formats.description}, {"with" if reorient else "without"} reorientation',
                  leave=False):
        cmd = ['mrconvert',
               op.join(indir, f'{acq}/'),
               op.join(outdir, f'{acq}.{formats.image_extension}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if formats.keyvalue_type == KeyvalueType.json:
            cmd.extend(['-json_export', op.join(outdir, f'{acq}.json')])
        if formats.grad_type == GradType.fsl:
            cmd.extend(['-export_grad_fsl', op.join(outdir, f'{acq}.bvec'), op.join(outdir, f'{acq}.bval')])
        elif formats.grad_type == GradType.b:
            cmd.extend(['-export_grad_mrtrix', op.join(outdir, f'{acq}.grad')])
        if formats.pe_type == PEType.table:
            cmd.extend(['-export_pe_table', op.join(outdir, f'{acq}.petable')])
        if formats.pe_type == PEType.topup:
            cmd.extend(['-export_pe_topup', op.join(outdir, f'{acq}.topup')])
        elif formats.pe_type == PEType.eddy:
            cmd.extend(['-export_pe_eddy', op.join(outdir, f'{acq}.eddycfg'), op.join(outdir, f'{acq}.eddyidx')])
        subprocess.run(cmd, check=True)




def run_intermediate(indir,
                     outdir,
                     formats_in,
                     formats_out,
                     reorient,
                     strides_option):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running {len(ACQUISITIONS)} instances of mrconvert from intermediate input:')
    logger.info(f'  Input {indir}, input formats {formats_in.description};')
    logger.info(f'  Output formats {formats_out.description}, reorient {reorient}, strides {strides_option}')
    for acq in tqdm(ACQUISITIONS,
                  desc='Running MRtrix3 mrconvert: '
                       f'{formats_in.description} -> {formats_out.description}, '
                       f'{"with" if reorient else "without"} reorientation, '
                       f'strides {strides_option}',
                  leave=False):
        cmd = ['mrconvert',
               op.join(indir, f'{acq}.{formats_in.image_extension}'),
               op.join(outdir, f'{acq}.{formats_out.image_extension}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if formats_in.keyvalue_type == KeyvalueType.json:
            cmd.extend(['-json_import', op.join(indir, f'{acq}.json')])
        if formats_in.grad_type == GradType.fsl:
            cmd.extend(['-fslgrad', op.join(indir, f'{acq}.bvec'), op.join(indir, f'{acq}.bval')])
        elif formats_in.grad_type == GradType.b:
            cmd.extend(['-grad', op.join(indir, f'{acq}.grad')])
        if formats_in.pe_type == PEType.table:
            cmd.extend(['-import_pe_table', op.join(indir, f'{acq}.petable')])
        elif formats_in.pe_type == PEType.topup:
            cmd.extend(['-import_pe_topup', op.join(indir, f'{acq}.topup')])
        elif formats_in.pe_type == PEType.eddy:
            cmd.extend(['-import_pe_eddy', op.join(indir, f'{acq}.eddycfg'), op.join(indir, f'{acq}.eddyidx')])
        if (formats_in.keyvalue_type != KeyvalueType.none and formats_out.keyvalue_type == KeyvalueType.json) \
                or (formats_in.pe_type != PEType.none and formats_out.pe_type == PEType.json):
            cmd.extend(['-json_export', op.join(outdir, f'{acq}.json')])
        if formats_in.grad_type != GradType.none:
            if formats_out.grad_type == GradType.fsl:
                cmd.extend(['-export_grad_fsl', op.join(outdir, f'{acq}.bvec'), op.join(outdir, f'{acq}.bval')])
            elif formats_out.grad_type == GradType.b:
                cmd.extend(['-export_grad_mrtrix', op.join(outdir, f'{acq}.grad')])
        if formats_in.pe_type != PEType.none:
            if formats_out.pe_type == PEType.table:
                cmd.extend(['-export_pe_table', op.join(outdir, f'{acq}.petable')])
            elif formats_out.pe_type == PEType.topup:
                cmd.extend(['-export_pe_topup', op.join(outdir, f'{acq}.topup')])
            elif formats_out.pe_type == PEType.eddy:
                cmd.extend(['-export_pe_eddy', op.join(outdir, f'{acq}.eddycfg'), op.join(outdir, f'{acq}.eddyidx')])
        if strides_option:
            cmd.extend(['-strides', strides_option])
        subprocess.run(cmd, check=True)

