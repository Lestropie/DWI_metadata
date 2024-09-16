#!/usr/bin/python3

import copy
import glob
import json
import logging
import numpy as np
import os
import os.path as op
import shutil
import subprocess
import sys


from collections import namedtuple
logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                    level=logging.INFO,
                    filename="log.log",
                    filemode="w")



# All possible configurations
# Need to handle diffusion gradient table vs. slice / phase encoding differently here:
# - Diffusion gradients are applied using the Device Coordinate System (DCS),
#   which for a patient in head first supine (HFS) results in:
#   - +X: Left     -> [-1, 0, 0] in RAS
#   - +Y: Anterior -> [ 0, 1, 0] in RAS
#   - +Z: Inferior -> [ 0, 0,-1] in RAS
# - Image encoding is based on the Patient Coordinate System (PCS),
#   which is independent of patient bedding:
#   - Sag+: Left      -> [-1, 0, 0] in RAS
#   - Cor+: Posterior -> [ 0,-1, 0] in RAS
#   - Tra+: Superior  -> [ 0, 0, 1] in RAS
PLANES = {
    'Tra': [ 0, 0, 1],
    'Cor': [ 0,-1, 0],
    'Sag': [-1, 0, 0]
}
SLICEORDERS = {
    'Asc': +1,
    'Des': -1,
}
PEDIRS = {
    'RL': [-1, 0, 0],
    'LR': [ 1, 0, 0],
    'AP': [ 0,-1, 0],
    'PA': [ 0, 1, 0],
    'HF': [ 0, 0,-1],
    'FH': [ 0, 0, 1]
}
GRADTABLE_FIDUCIALS = np.array([[-1, 0, 0],
                                [ 0, 1, 0],
                                [ 0, 0,-1]])



DIRECTION_CODES_ANATOMICAL = PEDIRS
DIRECTION_CODES_BIDS = {'i-': [-1, 0, 0],
                        'i':  [ 1, 0, 0],
                        'j-': [ 0,-1, 0],
                        'j':  [ 0, 1, 0],
                        'k-': [ 0, 0,-1],
                        'k':  [ 0, 0, 1]}


# Suspect that there may be an issue in MRtrix3 with handling of external metadata depending on the image format
# Therefore additionally test the scenario where NIfTI is *not* used, but JSON *is*
# The ".mih" case is used to test where metadata is embedded in the image header;
#   by using .mih rather than .mif, the raw text data can be read rather than using MRtrix3 commands
# TODO Make this a dictionary; give these lists names
EXTENSIONS = (['nii', 'json', 'bvec', 'bval'],
              ['mih'],
              ['mif', 'json'])
# Make sure we get complex non-standard strides that are both LHS and RHS coordinate systems
STRIDES = {'unmodified': None,
           'RAS': '+1,+2,+3,+4',
           'LAS': '-1,+2,+3,+4',
           'complexone': '-3,+1,-2,+4',
           'complextwo': '-3,+1,+2,+4',}



# Reduce computational burden of bedpostx
# Can't be run with zero burn-in, as the resulting orientations won't be anatomically faithful
# Default is burn-in b=1000, jumps j=1250, sample every s=25
BEDPOSTX_OPTIONS = ['-b', '500', '-j', '10', '-s', '5']



def code2direction(string, transform):
    try:
        return DIRECTION_CODES_ANATOMICAL[string]
    except KeyError:
        pass
    try:
        direction_imagespace = DIRECTION_CODES_BIDS[string]
    except KeyError as e:
        raise KeyError(f'Unexpected orientation encoding identifier "{string}"') from e
    direction_anatomical = [0, 0, 0]
    for index, row in enumerate(transform[0:3]):
        for axis in range(0, 3):
            direction_anatomical[index] += direction_imagespace[axis] * row[axis]
    return direction_anatomical
    


def get_transform(image_path):
    transform = subprocess.run(['mrinfo', image_path, '-transform',
                                '-config', 'RealignTransform', 'false',
                                '-quiet'],
                                capture_output=True,
                                text=True).stdout
    if not transform:
        raise FileNotFoundError(f'No transform read for "{image_path}"')
    transform = [[int(round(float(f))) for f in line.split()] for line in transform.splitlines()]
    return transform
    


# Generate set of all possible configurations
class Variant:
    def __init__(self, plane, sliceorder, pedir):
        self.plane = plane
        self.sliceorder = sliceorder
        self.pedir = pedir
    def __format__(self, fmt):
        return f'DWI_{self.plane}_{self.sliceorder}_{self.pedir}'

variants = []
for plane in PLANES:
    for pedir in PEDIRS:
        if not any(bool(a) and bool(b) for a, b in zip(PLANES[plane], PEDIRS[pedir])):
             for sliceorder in SLICEORDERS:
                variants.append(Variant(plane, sliceorder, pedir))
logger.debug('List of variants:')
for v in variants:
    logger.debug(f'  {v}')



def wipe_output_directory(dirpath):
    try:
        shutil.rmtree(dirpath)
    except OSError:
        pass
    os.makedirs(dirpath)



def run_dcm2niix(indir, outdir):
    indir = op.abspath(indir)
    cwd = os.getcwd()
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    os.chdir(indir)
    logger.info(f'Running {len(variants)} instances of dcm2niix')
    for v in variants:
        subprocess.run(['dcm2niix',
                        '-o', outdir,
                        '-f', '%f',
                        f'{v}'],
                       capture_output=True,
                       check=True)
    os.chdir(cwd)



def run_mrconvert_from_dicom(indir, outdir, extensions, reorient):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running {len(variants)} instances of mrconvert from DICOM:')
    logger.info(f'  File extensions {",".join(extensions)}, reorient {reorient}') 
    for v in variants:
        cmd = ['mrconvert',
               op.join(indir, f'{v}/'),
               op.join(outdir, f'{v}.{extensions[0]}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if 'json' in extensions:
            cmd.extend(['-json_export', op.join(outdir, f'{v}.json')])
        if 'bvec' in extensions and 'bval' in extensions:
            cmd.extend(['-export_grad_fsl', op.join(outdir, f'{v}.bvec'), op.join(outdir, f'{v}.bval')])
        subprocess.run(cmd, check=True)



def run_mrconvert_from_intermediate(indir,
                                    outdir,
                                    extensions_in,
                                    extensions_out,
                                    reorient,
                                    strides_option):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running {len(variants)} instances of mrconvert from intermediate input:')
    logger.info(f'  Input {indir}, input file extensions {",".join(extensions_in)};')
    logger.info(f'  Output file extensions {",".join(extensions_out)}, reorient {reorient}, strides {strides_option}')
    for v in variants:
        cmd = ['mrconvert',
               op.join(indir, f'{v}.{extensions_in[0]}'),
               op.join(outdir, f'{v}.{extensions_out[0]}'),
               '-config', 'RealignTransform', str(reorient),
               '-quiet']
        if 'json' in extensions_in:
            cmd.extend(['-json_import', op.join(indir, f'{v}.json')])
        if 'bvec' in extensions_in and 'bval' in extensions_in:
            cmd.extend(['-fslgrad', op.join(indir, f'{v}.bvec'), op.join(indir, f'{v}.bval')])
        if 'json' in extensions_out:
            cmd.extend(['-json_export', op.join(outdir, f'{v}.json')])
        if 'bvec' in extensions_out and 'bval' in extensions_out:
            cmd.extend(['-export_grad_fsl', op.join(outdir, f'{v}.bvec'), op.join(outdir, f'{v}.bval')])
        if strides_option:
            cmd.extend(['-strides', strides_option])
        subprocess.run(cmd, check=True)



def run_dwi2mask(indir, outdir, outpath):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    try:
        os.remove(outpath)
    except OSError:
        pass
    os.makedirs(outdir)
    logger.info(f'Running {len(variants)} instances of dwi2mask')
    mrmath_cmd = ['mrmath']
    for v in variants:
        out_path = op.join(outdir, f'{v}.mif')
        subprocess.run(['dwi2mask', 'legacy', op.join(indir, f'{v}/'), out_path,
                        '-config', 'RealignTransform', 'true',
                        '-quiet'],
                       check=True)
        mrmath_cmd.append(out_path)
    mrmath_cmd.extend(['max', outpath, '-datatype', 'bit', '-quiet'])
    subprocess.run(mrmath_cmd, check=True)
    logger.info(f'dwi2mask results aggregated as {outpath}')
    for v in variants:
        os.remove(op.join(outdir, f'{v}.mif'))
    


def convert_mask(indir, in_extension, maskpath, outdir, out_extension):
    try:
        shutil.rmtree(outdir)
    except OSError:
        pass
    os.makedirs(outdir)
    # Want to transform the aggregate mask image back to the originating image spaces
    # This is not fixed per variant; it depends on the image to which the mask is to be matched,
    #   and this could depend on the conversion software / whether or not MRtrix3 performed transform realignment
    logger.info(f'Converting aggregate mask to match {indir}')
    for v in variants:
        inpath = op.join(indir, f'{v}.{in_extension}')
        outpath = op.join(outdir, f'{v}.{out_extension}')
        if not op.exists(inpath):
            raise FileNotFoundError(f'Cannot convert mask for "{inpath}"')
        in_strides = subprocess.run(['mrinfo', inpath,
                                     '-strides',
                                     '-config', 'RealignTransform', 'true',
                                     '-quiet'],
                                    capture_output=True,
                                    text=True).stdout
        in_strides = [int(item) for item in in_strides.strip().split(' ')]
        out_strides = in_strides[0:3]
        subprocess.run(['mrconvert', maskpath, outpath,
                        '-strides', ','.join(map(str, out_strides)),
                        '-quiet'],
                       check=True)

    

def run_bedpostx(indir, maskdir, bedpostxdir):
    try:
        shutil.rmtree(bedpostxdir)
    except OSError:
        pass
    os.makedirs(bedpostxdir)
    indir = op.abspath(indir)
    maskdir = op.abspath(maskdir)
    cwd = os.getcwd()
    logger.info(f'Running {len(variants)} instances of bedpostx from input {indir}')
    os.chdir(bedpostxdir)
    for v in variants:
        bedpostx_tmpdir = f'{v}/'
        os.makedirs(bedpostx_tmpdir)
        os.symlink(op.join(indir, f'{v}.nii'), op.join(bedpostx_tmpdir, 'data.nii'))
        os.symlink(op.join(indir, f'{v}.bvec'), op.join(bedpostx_tmpdir, 'bvecs'))
        os.symlink(op.join(indir, f'{v}.bval'), op.join(bedpostx_tmpdir, 'bvals'))
        os.symlink(op.join(maskdir, f'{v}.nii'), op.join(bedpostx_tmpdir, 'nodif_brain_mask.nii'))
        subprocess.run(['bedpostx', bedpostx_tmpdir] + BEDPOSTX_OPTIONS,
                       check=True)
        for item in glob.glob(op.join(bedpostxdir, '*merged*')):
            os.remove(item)
    os.chdir(cwd)



def run_dwi2tensor(indir, extensions, maskdir, dwi2tensordir):
    try:
        shutil.rmtree(dwi2tensordir)
    except OSError:
        pass
    os.makedirs(dwi2tensordir)
    logger.info(f'Running {len(variants)} instances of dwi2tensor from input {indir}')
    for v in variants:
        tensor_image_path = op.join(dwi2tensordir, f'{v}_tensor.{extensions[0]}')
        mask_path = op.join(maskdir, f'{v}.{extensions[0]}')
        subprocess.run(['dwi2tensor', op.join(indir, f'{v}.{extensions[0]}'), tensor_image_path,
                        '-mask', mask_path,
                        '-quiet']
                       + (['-fslgrad', op.join(indir, f'{v}.bvec'), op.join(indir, f'{v}.bval')] if extensions[0] == 'nii' else []),
                       check=True)
        subprocess.run(['tensor2metric', tensor_image_path,
                        '-vector', op.join(dwi2tensordir, f'{v}_vector.{extensions[0]}'),
                        '-mask', mask_path,
                        '-modulate', 'fa',
                        '-quiet'],
                       check=True)
        os.remove(tensor_image_path)



def run_dtifit(indir, maskdir, dtifitdir):
    try:
        shutil.rmtree(dtifitdir)
    except OSError:
        pass
    os.makedirs(dtifitdir)
    logger.info(f'Running {len(variants)} instances of dtifit from input {indir}')
    for v in variants:
        subprocess.run(['dtifit',
                        '-k', op.join(indir, f'{v}.nii'),
                        '-o', op.join(dtifitdir, f'{v}'),
                        '-m', op.join(maskdir, f'{v}.nii'),
                        '-r', op.join(indir, f'{v}.bvec'),
                        '-b', op.join(indir, f'{v}.bval'),
                        '--wls',
                        '--save_tensor'],
                       capture_output=True,
                       check=True)
        subprocess.run(['mrcalc',
                        '-config', 'RealignTransform', 'false',
                        '-quiet',
                        op.join(dtifitdir, f'{v}_V1.nii.gz'),
                        op.join(dtifitdir, f'{v}_FA.nii.gz'),
                        '-mult',
                        op.join(dtifitdir, f'{v}.nii')],
                       check=True)
        for suffix in ('V1', 'V2', 'V3', 'FA', 'L1', 'L2', 'L3', 'MD', 'MO', 'S0'):
            os.remove(op.join(dtifitdir, f'{v}_{suffix}.nii.gz'))



def run_dtifit_to_mrtrix(dtifitdir, conversiondir):
    try:
        shutil.rmtree(conversiondir)
    except OSError:
        pass
    os.makedirs(conversiondir)
    logger.info(f'Converting {dtifitdir} to MRtrix3 format')
    for v in variants:
        subprocess.run(['peaksconvert',
                        op.join(dtifitdir, f'{v}.nii'),
                        op.join(conversiondir, f'{v}.mif'),
                        '-in_format', '3vector',
                        '-in_reference', 'bvec',
                        '-out_format', '3vector',
                        '-out_reference', 'xyz',
                        '-quiet'],
                       check=True)



def run_bedpostx_to_mrtrix(bedpostxdir, conversiondir, use_dyads):
    try:
        shutil.rmtree(conversiondir)
    except OSError:
        pass
    os.makedirs(conversiondir)
    logger.info(f'Converting {bedpostxdir} to MRtrix3 format')
    for v in variants:
        bedpostx_subdir = os.path.join(bedpostxdir, f'{v}.bedpostX')
        tmppath = op.join(conversiondir, 'tmp.mif')
        if use_dyads:
            for index in range(1, 4):
                subprocess.run(['mrcalc',
                                op.join(bedpostx_subdir, f'dyads{index}.nii.gz'),
                                op.join(bedpostx_subdir, f'mean_f{index}samples.nii.gz'),
                                '-mult',
                                op.join(conversiondir, f'tmp{index}.mif'),
                                '-config', 'RealignTransform', 'false',
                                '-quiet'],
                               check=True)
            subprocess.run(['mrcat',
                            op.join(conversiondir, 'tmp1.mif'),
                            op.join(conversiondir, 'tmp2.mif'),
                            op.join(conversiondir, 'tmp3.mif'),
                            tmppath,
                            '-axis', '3',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            for index in range(1, 4):
                os.remove(op.join(conversiondir, f'tmp{index}.mif'))
            subprocess.run(['peaksconvert',
                            tmppath,
                            op.join(conversiondir, f'{v}.mif'),
                            '-in_format', '3vector',
                            '-in_reference', 'bvec',
                            '-out_format', '3vector',
                            '-out_reference', 'xyz',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            os.remove(tmppath)
        else:
            subprocess.run(['mrcat',
                            op.join(bedpostx_subdir, 'mean_f1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th1samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_f2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th2samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_f3samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_ph3samples.nii.gz'),
                            op.join(bedpostx_subdir, 'mean_th3samples.nii.gz'),
                            tmppath,
                            '-axis', '3',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            subprocess.run(['peaksconvert',
                            tmppath,
                            op.join(conversiondir, f'{v}.mif'),
                            '-in_format', 'spherical',
                            '-in_reference', 'bvec',
                            '-out_format', '3vector',
                            '-out_reference', 'xyz',
                            '-config', 'RealignTransform', 'false',
                            '-quiet'],
                           check=True)
            os.remove(tmppath)
        
                        
                        
                        
                        
                        
                        
               
MetadataMismatch = namedtuple('MetadataMismatch', 'variant metadata_code metadata_reversal metadata_direction description_code description_reversal description_direction transform')

def verify_metadata(testname, inputdir, file_extensions):
    sliceencodingdirection_errors = []
    phaseencodingdirection_errors = []
    gradtable_errors = []
    logger.debug(f'Verifying metadata for {testname}:')
    for v in variants:
        logger.debug(f'  Variant {v}:')
        if 'json' in file_extensions:
            with open(op.join(inputdir, f'{v}.json'), 'r') as f:
                metadata = json.loads(f.read())
            slicetimingreversal_metadata = metadata['SliceTiming'][0] > metadata['SliceTiming'][-1]
            transform = get_transform(op.join(inputdir, f'{v}.{file_extensions[0]}'))
            dw_scheme = metadata.get('dw_scheme', None)
        else:
            assert file_extensions == ['mih']
            metadata = {}
            with open(op.join(inputdir, f'{v}.{file_extensions[0]}'), 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == 'mrtrix image':
                        continue
                    line_split = line.split(': ')
                    if len(line_split) != 2:
                        line_split = [line_split[0], ': '.join(line_split[1:])]
                    if line_split[0] in metadata:
                        if isinstance(metadata[line_split[0]], list):
                            metadata[line_split[0]].append(line_split[1])
                        else:
                            metadata[line_split[0]] = [metadata[line_split[0]], line_split[1]]
                    else:
                        metadata[line_split[0]] = line_split[1]
            slicetiming_metadata = [float(f) for f in metadata['SliceTiming'].split(',')]
            slicetimingreversal_metadata = slicetiming_metadata[0] > slicetiming_metadata[-1]
            transform = [ [int(round(float(f))) for f in line.split(',')] for line in metadata['transform'] ]
        if 'nii' in file_extensions:
            with open(op.join(inputdir, f'{v}.bvec'), 'r') as f:
                bvecs = [[float(value) for value in line.split(' ')] for line in f.readlines()]
            dw_scheme = None
        else:
            bvecs = None
            if 'mih' in file_extensions:
                dw_scheme = [ [float(f) for f in line.split(',')] for line in metadata['dw_scheme'] ]
        
        # Slice encoding direction not explicitly labelled in dcm2niix JSON;
        #   therefore if absent we'll have to assume "k"
        if 'SliceEncodingDirection' not in metadata:
            if 'dcm2niix' in inputdir:
                metadata['SliceEncodingDirection'] = 'k'
            else:
                raise KeyError('"SliceEncodingDirection" missing from ' + op.join(inputdir, f'{v}'))
        
        sliceencodingdirection_metadata = code2direction(metadata['SliceEncodingDirection'], transform)
        if slicetimingreversal_metadata:
            sliceencodingdirection_metadata = [-i if i else 0 for i in sliceencodingdirection_metadata]
        phaseencodingdirection_metadata = code2direction(metadata['PhaseEncodingDirection'], transform)
        
        sliceencodingdirection_seriesdescription = [i * SLICEORDERS[v.sliceorder] for i in PLANES[v.plane]]
        phaseencodingdirection_seriesdescription = PEDIRS[v.pedir]
        
        if sliceencodingdirection_metadata != sliceencodingdirection_seriesdescription:
            sliceencodingdirection_errors.append(MetadataMismatch(f'{v}',
                                                          metadata['SliceEncodingDirection'],
                                                          slicetimingreversal_metadata,
                                                          sliceencodingdirection_metadata,
                                                          v.plane,
                                                          SLICEORDERS[v.sliceorder],
                                                          sliceencodingdirection_seriesdescription,
                                                          transform))
        if phaseencodingdirection_metadata != phaseencodingdirection_seriesdescription:
            phaseencodingdirection_errors.append(MetadataMismatch(f'{v}',
                                                          metadata['PhaseEncodingDirection'],
                                                          False,
                                                          phaseencodingdirection_metadata,
                                                          v.pedir,
                                                          False,
                                                          phaseencodingdirection_seriesdescription,
                                                          transform))
        
        if dw_scheme:
            fiducials = np.array([[int(round(f)) for f in dw_scheme[row][0:3]] for row in range(1, 4)])
            if not np.array_equal(fiducials, GRADTABLE_FIDUCIALS):
                gradtable_errors.append([f'{v}', fiducials])
        else:
            assert bvecs
            # Figure out how to validate bvecs
            # Ideally do this based on description of the format,
            #   rather than relying on MRtrix3 commands,
            #   given that we may need to use this test to validate the latter
            #
            # Skip the first b=0 volume
            bvecs_fiducials = np.array([row[1:4] for row in bvecs])
            logger.debug(f'    Stored bvec fiducials: {bvecs_fiducials.round()}')
            transform_linear = np.array([row[0:3] for row in transform[0:3]])
            logger.debug('    Transform: ' + str(transform_linear.round()))
            #sys.stderr.write('transform_linear: ' + str(transform_linear) + '\n')
            # We transpose the vectors so that they can be premultiplied by the transform matrix
            fiducials_image = np.transpose(bvecs_fiducials)
            # Invert the first element of each 3-vector if necessary
            if np.linalg.det(transform_linear) > 0.0:
                fiducials_image[:,0] *= -1.0
            logger.debug(f'    Transposed & flipped imagespace fiducials: {fiducials_image.round()}')
            # Transform fiducials from being defined with respect to image axes
            #   to being defined with respect to scanner axes
            #fiducials_real = np.matmul(transform_linear, fiducials_image).round()
            fiducials_real = np.zeros((3,3))
            for gradindex in range(0,3):
                fiducials_real[gradindex] = np.dot(transform_linear, fiducials_image[gradindex,:])
            #sys.stderr.write('Transform from bvecs ' + str(bvecs_fiducials) + ' to imagespace' + str(fiducials_image) + ' to scannerspace ' + str(fiducials_real) + '\n')
            logger.debug('    Realspace fiducials: ' + str(fiducials_real.round()))
            if not np.array_equal(fiducials_real.round(), GRADTABLE_FIDUCIALS):
                gradtable_errors.append([f'{v}', fiducials_real])
    
    logger.info(f'Results for {testname}:')
    if sliceencodingdirection_errors:
        logger.warning(f'{len(sliceencodingdirection_errors)} errors in slice encoding direction for {testname}:')
        for mismatch in sliceencodingdirection_errors:
            logger.warning(f'  {mismatch.variant}: "{mismatch.metadata_code}" x {-1 if mismatch.metadata_reversal else 1}; transform: {mismatch.transform[0:3]} = {mismatch.metadata_direction} != "{mismatch.description_code}" x {mismatch.description_reversal} = {mismatch.description_direction}')
    else:
        logger.info('No slice encoding direction errors')
    if phaseencodingdirection_errors:
        logger.warning(f'{len(phaseencodingdirection_errors)} errors in phase encoding direction for {testname}:')
        for mismatch in phaseencodingdirection_errors:
            logger.warning(f'  {mismatch.variant}: "{mismatch.metadata_code}"; transform: {mismatch.transform[0:3]} = {mismatch.metadata_direction} != "{mismatch.description_code}" = {mismatch.description_direction}')
    else:
        logger.info('No phase encoding direction errors')
    if gradtable_errors:
        logger.warning(f'{len(gradtable_errors)} errors in gradient table for {testname}:')
        for mismatch in gradtable_errors:
            if np.array_equal(mismatch[1].round() * -1, GRADTABLE_FIDUCIALS):
                logger.warning(f'  {mismatch[0]}: ANTIPODAL')
            else:
                logger.warning(f'  {mismatch[0]}: {mismatch[1]}')
    else:
        logger.info('No gradient table errors')
    return

                        
                        
                        
                        
                        
                        
def verify_peaks(testname, inputdir):
    errors = []
    logger.info(f'Verifying peak orientations for {testname}')
    for v in variants:            
        logger.debug(f'  Variant {v}')
        proc = subprocess.run(['peakscheck', op.join(inputdir, f'{v}.mif'), '-quiet'])
        if proc.returncode != 0:
            errors.append(f'{v}')
    if errors:
        logger.warning(f'{len(errors)} potential errors in fibre orientations for {testname}: {errors}')
        
                        
                        
                        
                        
                        

def main():
    dicomdir = sys.argv[1]
    scratchdir = sys.argv[2]

    if not op.isdir(dicomdir):
        sys.stderr.write('Expect first argument to be input directory')
        sys.exit(1)

    wipe_output_directory(scratchdir)
    try:
        os.makedirs(scratchdir)
    except FileExistsError:
        pass
    
    dcm2niixdir = op.join(scratchdir, 'dcm2niix')
    run_dcm2niix(dicomdir, os.path.abspath(dcm2niixdir))
    verify_metadata('dcm2niix', dcm2niixdir, ('nii', 'json'))
    
    # Evaluate MRtrix conversion from DICOM to various formats
    for extensions in EXTENSIONS:
        for reorient in (False, True):
            outdir = op.join(scratchdir, f'mrconvert_dcm2{"".join(extensions)}{reorient}')
            run_mrconvert_from_dicom(dicomdir,
                                     outdir,
                                     extensions,
                                     reorient)
            verify_metadata(f'mrconvert: DICOM to {",".join(extensions)} {"with" if reorient else "without"} reorientation',
                            outdir,
                            extensions)
    
    # To better separate potential issues between MRtrix3 read and MRtrix3 write,
    #   evaluate conversions from dcm2niix to different formats with different strides
    for extensions in EXTENSIONS:
        for reorient in (False, True):
            for strides_name, strides_option in STRIDES.items():
                outdir = op.join(scratchdir, f'dcm2niix2{"".join(extensions)}{reorient}{strides_name}')
                run_mrconvert_from_intermediate(dcm2niixdir,
                                                outdir,
                                                ['nii', 'json', 'bvec', 'bval'],
                                                extensions,
                                                reorient,
                                                strides_option)
                verify_metadata(f'dcm2niix to {",".join(extensions)} {"with" if reorient else "without"} reorientation & {strides_name} strides',
                                outdir,
                                extensions)
                shutil.rmtree(outdir)
    
    # Now take files that have been converted by MRtrix3 from DICOM to some format,
    #   and import them and write them as another format
    for extensions_intermediate in EXTENSIONS:
        for reorient_intermediate in (False, True):
            intermediatedir = op.join(scratchdir, f'mrconvert_dcm2{"".join(extensions_intermediate)}{reorient_intermediate}')
            for extensions_out in EXTENSIONS:
                for reorient_out in (False, True):
                    for strides_name, strides_option in STRIDES.items():
                        outdir = op.join(scratchdir, f'mrconvert_{"".join(extensions_intermediate)}{reorient_intermediate}2{"".join(extensions_out)}{reorient_out}{strides_name}')
                        run_mrconvert_from_intermediate(intermediatedir,
                                                        outdir,
                                                        extensions_intermediate,
                                                        extensions_out,
                                                        reorient_out,
                                                        strides_option)
                        verify_metadata(f'mrconvert: {",".join(extensions_intermediate)} {"with" if reorient_intermediate else "without"} reorientation to {",".join(extensions_out)} {"with" if reorient_out else "without"} reorientation & {strides_name} strides',
                                        outdir,
                                        extensions_out)
                        shutil.rmtree(outdir)
                                            
               
                          
    # Generate a single brain mask
    #   that will be used for processing of all datasets    
    dwi2maskdir = op.join(scratchdir, 'dwi2mask')
    maskpath = op.join(scratchdir, 'mask.nii')
    run_dwi2mask(dicomdir, dwi2maskdir, maskpath) 
    convert_mask(dcm2niixdir, 'nii', maskpath, op.join(scratchdir, 'mask_dcm2niix'), 'nii')
    for extensions in EXTENSIONS:
        for reorient in (False, True):
            version_string = f'dcm2{"".join(extensions)}{reorient}'
            mrtrixdir = op.join(scratchdir, f'mrconvert_{version_string}')    
            convert_mask(mrtrixdir, extensions[0], maskpath, op.join(scratchdir, f'mask_mrconvert_{version_string}'), extensions[0])
    
    # Run tensor fits using both MRtrix3 and FSL
    dwi2tensordir = op.join(scratchdir, 'dwi2tensor_from_dcm2niix')
    maskdir = op.join(scratchdir, 'mask_dcm2niix')
    run_dwi2tensor(dcm2niixdir, ['nii', 'json'], maskdir, dwi2tensordir)
    for extensions in EXTENSIONS:
        for reorient in (False, True):
            version_string = f'dcm2{"".join(extensions)}{reorient}'
            mrconvertdir = op.join(scratchdir, f'mrconvert_{version_string}')
            maskdir = op.join(scratchdir, f'mask_mrconvert_{version_string}')
            dwi2tensordir = op.join(scratchdir, f'dwi2tensor_from_mrconvert_{version_string}')
            run_dwi2tensor(mrconvertdir, extensions, maskdir, dwi2tensordir)

    dtifitdir = op.join(scratchdir, 'dtifit_from_dcm2niix')
    maskdir = op.join(scratchdir, 'mask_dcm2niix')
    run_dtifit(dcm2niixdir, maskdir, dtifitdir)
    for reorient in (False, True):
        mrconvertdir = op.join(scratchdir, f'mrconvert_dcm2niijsonbvecbval{reorient}')
        maskdir = op.join(scratchdir, f'mask_mrconvert_dcm2niijsonbvecbval{reorient}')
        dtifitdir = op.join(scratchdir, f'dtifit_from_mrconvert{reorient}')
        run_dtifit(mrconvertdir, maskdir, dtifitdir)
    
    # TODO Use peakscheck on MRtrix tensor estimates?
    # We already know those are using our own convention...
    
    # Evaluate dtifit outputs
    # If our interpretation of the vector orientations provided by FSL dtifit is correct,
    #   then we should be able to transform them to scanner space,
    #   and they should look appropriate in mrview
    dtifitdir = op.join(scratchdir, 'dtifit_from_dcm2niix')
    conversiondir = op.join(scratchdir, 'dtifit_dcm2niix_to_scannerspace')
    run_dtifit_to_mrtrix(dtifitdir, conversiondir)
    verify_peaks('FSL dtifit from dcm2niix data', conversiondir)
    for reorient in (False, True):
        dtifitdir = op.join(scratchdir, f'dtifit_from_mrconvert{reorient}')
        conversiondir = op.join(scratchdir, f'dtifit_mrconvert{reorient}_to_scannerspace')
        run_dtifit_to_mrtrix(dtifitdir, conversiondir)
        verify_peaks(f'FSL dtifit from mrconvert data {"with" if reorient else "without"} reorientation', conversiondir)
    
    # Run bedpostx
    # Need to run on data generated from both dcm2niix and MRtrix3
    bedpostxdir = op.join(scratchdir, 'bedpostx_from_dcm2niix')
    maskdir = op.join(scratchdir, 'mask_dcm2niix')
    run_bedpostx(dcm2niixdir, maskdir, bedpostxdir)
    for reorient in (False, True):
        mrtrixdir = op.join(scratchdir, f'mrconvert_dcm2niijsonbvecbval{reorient}')
        maskdir = op.join(scratchdir, f'mask_mrconvert_dcm2niijsonbvecbval{reorient}')
        bedpostxdir = op.join(scratchdir, f'bedpostx_from_mrconvert{reorient}')
        run_bedpostx(mrtrixdir, maskdir, bedpostxdir)
    
    # Evaluate bedpostx outputs
    # Note that fsleyes labels "L-R-A-P-S-I" do *not* correspond to anatomical orientations;
    #   they seemingly correspond rather to i, i-, j, j-, k, k-
    # Convert bedpostx mean fits to 3-vectors
    bedpostxdir = op.join(scratchdir, 'bedpostx_from_dcm2niix')
    conversiondir = op.join(scratchdir, 'bedpostx_dcm2niix_sph2peaks')
    run_bedpostx_to_mrtrix(bedpostxdir, conversiondir, False)
    verify_peaks('bedpostx from dcm2niix; spherical coordinates', conversiondir)
    conversiondir = op.join(scratchdir, 'bedpostx_dcm2niix_dyads2peaks')
    run_bedpostx_to_mrtrix(bedpostxdir, conversiondir, True)
    verify_peaks('bedpostx from dcm2niix; 3-vectors', conversiondir)
    for reorient in (False, True):
        bedpostxdir = op.join(scratchdir, f'bedpostx_from_mrconvert{reorient}')
        conversiondir = op.join(scratchdir, f'bedpostx_mrconvert{reorient}_sph2peaks')
        run_bedpostx_to_mrtrix(bedpostxdir, conversiondir, False)
        verify_peaks(f'bedpostx from mrconvert {"with" if reorient else "without"} reorientation; spherical coordinates', conversiondir)
        conversiondir = op.join(scratchdir, f'bedpostx_mrconvert{reorient}_dyads2peaks')
        run_bedpostx_to_mrtrix(bedpostxdir, conversiondir, True)
        verify_peaks(f'bedpostx from mrconvert {"with" if reorient else "without"} reorientation; 3-vectors', conversiondir)
    
    
    


if __name__ == '__main__':
    main()

