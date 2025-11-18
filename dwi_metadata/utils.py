#!/usr/bin/python3

import os
import shutil
import subprocess

from dwi_metadata import DIRECTION_CODES_ANATOMICAL
from dwi_metadata import DIRECTION_CODES_BIDS



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
        if os.path.exists(image_path):
            raise ValueError(f'Unable to read transform from "{image_path}"')
        raise FileNotFoundError(f'No transform read for "{image_path}" as file does not exist')
    try:
        transform = [[int(round(float(f))) for f in line.split()] for line in transform.splitlines()]
    except ValueError as exc:
        raise ValueError(f'Error interpreting transform from image "{image_path}"') from exc
    return transform



def wipe_output_directory(dirpath):
    try:
        for root, dirs, files in os.walk(dirpath):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))
    except FileNotFoundError:
        pass
    try:
        os.makedirs(dirpath)
    except FileExistsError:
        pass

