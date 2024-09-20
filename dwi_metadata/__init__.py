#!/usr/bin/python3

import itertools
import numpy as np

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

# The ".mih" case is used to test where metadata is embedded in the image header;
#   by using .mih rather than .mif, the raw text data can be read rather than using MRtrix3 commands
EXTENSIONS = (['nii', 'json', 'bvec', 'bval'],
              ['mih'],
              ['mif', 'json', 'grad'])

# Generate set of all possible configurations
class Variant:
    def __init__(self, plane, sliceorder, pedir):
        self.plane = plane
        self.sliceorder = sliceorder
        self.pedir = pedir
    def __format__(self, fmt):
        return f'DWI_{self.plane}_{self.sliceorder}_{self.pedir}'
VARIANTS = []
for plane, pedir, sliceorder in itertools.product(PLANES, PEDIRS, SLICEORDERS):
    if not any(bool(a) and bool(b) for a, b in zip(PLANES[plane], PEDIRS[pedir])):
        VARIANTS.append(Variant(plane, sliceorder, pedir))

