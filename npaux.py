#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import numpy as np

# == sequence_segmentation ==
# Generate all segments of length segment_length from sequence, optionally with prefixed segments
def sequence_segmentation (sequence, segment_length, prefix = None):
  L = len (sequence)
  segments = []
  if prefix != None:
    for i in range (segment_length-1, 0, -1):
      if len (sequence) >= segment_length - i:
        seg = np.concatenate ((i * [prefix], sequence[0:segment_length - i]))
        segments.append (seg)
  for i in range (L - segment_length + 1):
    seg = sequence[i:i + segment_length]
    segments.append (seg)
  return segments
assert np.prod (sequence_segmentation (10 + np.arange (5), 4, -1) ==    # [10, 11, 12, 13, 14]
                np.array ([[-1, -1, -1, 10], [-1, -1, 10, 11],
                           [-1, 10, 11, 12], [10, 11, 12, 13], [11, 12, 13, 14]]))
