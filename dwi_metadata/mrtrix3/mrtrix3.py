#!/usr/bin/python3

import itertools
import logging
import os
from os import path as op
import shutil
import subprocess
from tqdm import tqdm
import numpy

from dwi_metadata import FILE_FORMATS
from dwi_metadata import ACQUISITIONS
from dwi_metadata import GradType
from dwi_metadata import KeyvalueType
from dwi_metadata import PEType
from dwi_metadata import tests

from . import dwi2mask
from . import dwi2tensor
from . import mrconvert

logger = logging.getLogger(__name__)


# Make sure we get complex non-standard strides that are both LHS and RHS coordinate systems
STRIDES = {'unmodified': None,
           'RAS': '+1,+2,+3,+4',
           'LAS': '-1,+2,+3,+4',
           'complexone': '-3,+1,-2,+4',
           'complextwo': '-3,+1,+2,+4',}



def test_mrconvert_from_dicom(dicomdir, scratchdir):
    for formats, reorient in tqdm(itertools.product(FILE_FORMATS, (False, True)),
                                     desc='Evaluating MRtrix3 mrconvert from DICOM',
                                     total=len(FILE_FORMATS)*2):
        outdir = op.join(scratchdir, f'mrconvert_dcm2{"".join(formats.symbolic_name)}{reorient}')
        mrconvert.run_dicom(dicomdir,
                            outdir,
                            formats,
                            reorient)
        tests.metadata(f'mrconvert: DICOM to {formats.description} '
                       f'{"with" if reorient else "without"} reorientation',
                       outdir,
                       formats,
                       tests.MetadataTests(formats.grad_type != GradType.none,
                                           formats.pe_type != PEType.none,
                                           formats.keyvalue_type != KeyvalueType.none))



def test_mrconvert_from_dcm2niix(dcm2niixdir, scratchdir):
    for formats, reorient, (strides_name, strides_option) in \
        tqdm(itertools.product(FILE_FORMATS, (False, True), STRIDES.items()),
             desc='Evaluating MRtrix3 mrconvert from dcm2niix',
             total=len(FILE_FORMATS)*2*len(STRIDES)):

        outdir = op.join(scratchdir, f'dcm2niix2{formats.symbolic_name}{reorient}{strides_name}')
        mrconvert.run_intermediate(dcm2niixdir,
                                   outdir,
                                   FILE_FORMATS[0],
                                   formats,
                                   reorient,
                                   strides_option)
        tests.metadata(f'mrconvert: dcm2niix to {formats.description} '
                       f'{"with" if reorient else "without"} reorientation '
                       f'& {strides_name} strides',
                       outdir,
                       formats,
                       tests.MetadataTests(formats.grad_type != GradType.none,
                                           formats.pe_type != PEType.none,
                                           formats.keyvalue_type != KeyvalueType.none))
        shutil.rmtree(outdir)




def test_mrconvert_from_mrconvert(scratchdir):
    for formats_intermediate, reorient_intermediate, formats_out, reorient_out, (strides_name, strides_option) \
        in tqdm(itertools.product(FILE_FORMATS, (False, True), FILE_FORMATS, (False, True), STRIDES.items()),
                desc='Evaluating MRtrix3 mrconvert from multiple formats with stride manipulation',
                total=len(FILE_FORMATS)*2*len(FILE_FORMATS)*2*len(STRIDES)):

        # Some combinations of input and output we can skip as there's no tests to do
        if not (formats_intermediate.grad_type != GradType.none and formats_out.grad_type != GradType.none \
                or formats_intermediate.pe_type != PEType.none and formats_out.pe_type != PEType.none \
                or formats_intermediate.keyvalue_type != KeyvalueType.none and formats_out.keyvalue_type != KeyvalueType.none):
            continue

        intermediatedir = op.join(scratchdir, f'mrconvert_dcm2{formats_intermediate.symbolic_name}{reorient_intermediate}')
        outdir = op.join(scratchdir, f'mrconvert_{formats_intermediate.symbolic_name}{reorient_intermediate}'
                                     f'2{"".join(formats_out.symbolic_name)}{reorient_out}{strides_name}')
        mrconvert.run_intermediate(intermediatedir,
                                   outdir,
                                   formats_intermediate,
                                   formats_out,
                                   reorient_out,
                                   strides_option)
        tests.metadata(f'mrconvert: {formats_intermediate.description} '
                       f'{"with" if reorient_intermediate else "without"} reorientation '
                       f'to {formats_out.description} '
                       f'{"with" if reorient_out else "without"} reorientation '
                       f'& {strides_name} strides',
                       outdir,
                       formats_out,
                       tests.MetadataTests(formats_intermediate.grad_type != GradType.none and formats_out.grad_type != GradType.none,
                                           formats_intermediate.pe_type != PEType.none and formats_out.pe_type != PEType.none,
                                           formats_intermediate.keyvalue_type != KeyvalueType.none and formats_out.keyvalue_type != KeyvalueType.none))
        shutil.rmtree(outdir)



def test_petables(dicomdir, scratchdir):
    os.makedirs(op.join(scratchdir, 'petables'))
    temp_image_path = op.join(scratchdir, 'petables', 'temp.mif')
    errors = []
    for acq, reorient in tqdm(itertools.product(ACQUISITIONS, (False, True)),
                              desc='Testing PE table import/export',
                              total=len(ACQUISITIONS)*2):
        reftable_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}.txt')
        subprocess.run(['mrinfo',
                        op.join(dicomdir, f'{acq}'),
                        '-export_pe_table', reftable_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        reftable_data = numpy.loadtxt(reftable_path)
        # For exporting table to file,
        #   may be different behaviour depending on whether output image path is NIfTI or other;
        #   therefore need to test both
        table_nii_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_nifti.table')
        table_nii_image_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_table.nii')
        subprocess.run(['mrconvert',
                        op.join(dicomdir, f'{acq}'),
                        table_nii_image_path,
                        '-export_pe_table', table_nii_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        table_mif_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_mrtrix.table')
        table_mif_image_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_table.mif')
        subprocess.run(['mrconvert',
                        op.join(dicomdir, f'{acq}'),
                        table_mif_image_path,
                        '-export_pe_table', table_mif_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        topup_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}.topup')
        topup_image_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_topup.nii')
        subprocess.run(['mrconvert',
                        op.join(dicomdir, f'{acq}'),
                        topup_image_path,
                        '-export_pe_topup', topup_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        eddycfg_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}.cfg')
        eddyidx_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}.idx')
        eddy_image_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_eddy.nii')
        subprocess.run(['mrconvert',
                        op.join(dicomdir, f'{acq}'),
                        eddy_image_path,
                        '-export_pe_eddy', eddycfg_path, eddyidx_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        # TODO Produce a version of the image that does not contain phase encoding information
        #   (Or use one that has been pre-generated elsewhere)
        from_table_nii_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_fromtable_nii.txt')
        from_table_mif_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_fromtable_mif.txt')
        from_topup_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_fromtopup.txt')
        from_eddy_path = op.join(scratchdir, 'petables', f'{acq}_{reorient}_fromeddy.txt')
        subprocess.run(['mrconvert',
                        table_nii_image_path,
                        temp_image_path,
                        '-import_pe_table', table_nii_path,
                        '-export_pe_table', from_table_nii_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        os.remove(temp_image_path)
        # TODO Necessary to first wipe the phase encoding information from the .mif header?
        subprocess.run(['mrconvert',
                        table_mif_image_path,
                        temp_image_path,
                        '-import_pe_table', table_mif_path,
                        '-export_pe_table', from_table_mif_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        os.remove(temp_image_path)
        subprocess.run(['mrconvert',
                        topup_image_path,
                        temp_image_path,
                        '-import_pe_topup', topup_path,
                        '-export_pe_table', from_topup_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        os.remove(temp_image_path)
        subprocess.run(['mrconvert',
                        eddy_image_path,
                        temp_image_path,
                        '-import_pe_eddy', eddycfg_path, eddyidx_path,
                        '-export_pe_table', from_eddy_path,
                        '-config', 'RealignTransform', f'{reorient}',
                        '-quiet'],
                       check=True)
        os.remove(temp_image_path)
        from_table_nii_data = numpy.loadtxt(from_table_nii_path)
        from_table_mif_data = numpy.loadtxt(from_table_mif_path)
        from_topup_data = numpy.loadtxt(from_topup_path)
        from_eddy_data = numpy.loadtxt(from_eddy_path)
        if not numpy.array_equal(reftable_data, from_table_nii_data):
            errors.append((f'{acq}', reorient, 'table_nii'))
        if not numpy.array_equal(reftable_data, from_table_mif_data):
            errors.append((f'{acq}', reorient, 'table_mif'))
        if not numpy.array_equal(reftable_data, from_topup_data):
            errors.append((f'{acq}', reorient, 'topup'))
        if not numpy.array_equal(reftable_data, from_eddy_data):
            errors.append((f'{acq}', reorient, 'eddy'))

    if errors:
        logger.error(f'{len(errors)} errors found in phase encoding table handling:')
        for error in errors:
            logger.error(f'  {error[0]}, {"with" if error[1] else "without"} reorientation, converted to {error[2]}')



def convert_mask(dcm2niixdir, maskpath, scratchdir):
    dwi2mask.convert(dcm2niixdir,
                     'nii',
                     maskpath,
                     op.join(scratchdir, 'mask_dcm2niix'),
                     'nii')
    for formats, reorient in tqdm(itertools.product(FILE_FORMATS, (False, True)),
                                     desc='Back-propagating brain mask to MRtrix3 mrconvert outputs'):
        version_string = f'dcm2{formats.symbolic_name}{reorient}'
        mrtrixdir = op.join(scratchdir, f'mrconvert_{version_string}')
        dwi2mask.convert(mrtrixdir,
                         formats.image_extension,
                         maskpath,
                         op.join(scratchdir, f'mask_mrconvert_{version_string}'),
                         formats.image_extension)



def test_dwi2tensor(scratchdir):
    dwi2tensor.run(op.join(scratchdir, 'dcm2niix'),
                   FILE_FORMATS[0],
                   op.join(scratchdir, 'mask_dcm2niix'),
                   op.join(scratchdir, 'dwi2tensor_from_dcm2niix'))
    tests.peaks(f'MRtrix3 dwi2tensor from dcm2niix',
                op.join(scratchdir, 'dwi2tensor_from_dcm2niix'),
                op.join(scratchdir, 'mask_dcm2niix'),
                'nii',
                'nii')
    for formats, reorient in tqdm(itertools.product(FILE_FORMATS, (False, True)),
                                     desc='Running MRtrix3 dwi2tensor on MRtrix3 mrconvert outputs',
                                     total=len(FILE_FORMATS)*2):
        if formats.grad_type == GradType.none:
            continue
        version_string = f'dcm2{formats.symbolic_name}{reorient}'
        outdir = op.join(scratchdir, f'dwi2tensor_from_mrconvert_{version_string}')
        maskdir = op.join(scratchdir, f'mask_mrconvert_{version_string}')
        dwi2tensor.run(op.join(scratchdir, f'mrconvert_{version_string}'),
                       formats,
                       maskdir,
                       outdir)
        tests.peaks(f'MRtrix3 dwi2tensor from mrconvert {version_string}',
                    outdir,
                    maskdir,
                    formats.image_extension,
                    formats.image_extension)

