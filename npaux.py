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

# == sequence_list_segmentation ==
# Generate all segments of given length from a list of sequences
def sequence_list_segmentation (sequence_list, segment_length, prefix = None):
  all_segments = []
  for j, sequence in enumerate (sequence_list):
    segments = sequence_segmentation (sequence, segment_length, prefix)
    all_segments += segments
  return np.stack (all_segments, axis = 0)

# == make_rows_unique ==
# Remove non-unique rows from `array`, possibly inspecting `duparray` to determine uniqueness.
def make_rows_unique (array, duparray = None):
  array = np.array (array)
  duparray = array if duparray is None else np.array (duparray)
  assert array.shape[0] == duparray.shape[0]
  unique_rows, unique_indices = np.unique (duparray, axis = 0, return_index = True)
  del unique_rows
  unique_indices = sorted (unique_indices)                      # reconstruct original order
  array = array[unique_indices]
  return array

# == softmax ==
def softmax (vec):
  vec = np.asarray (vec, dtype = np.float64)
  exp_vec = np.exp (vec)
  softmax_dist = exp_vec / sum (exp_vec)
  return softmax_dist

# == reweight_distribution ==
# Adjust entropy of a softmax distribution with temperature, use values > 1.0 to increase.
def reweight_distribution (normalized_dist, temperature):
  # use masked array to ignore values <= 0
  distribution = np.ma.log (normalized_dist) / temperature
  distribution = np.exp (distribution)
  # restore 0.0 in masked array
  distribution.data[distribution.mask] = 0
  distribution = distribution.data
  # renormalize if not 0.0
  dsum = np.sum (distribution)
  if dsum > 0.0:
    distribution = distribution / dsum
  return distribution
assert ((abs (reweight_distribution ([0.4,0.6], 1.1) -0.5) < 0.092).all())

# == top_k_filter ==
# Assign `filler` to all elements in `array` except for the top-k.
def top_k_filter (array, k, filler = 0):
  # See: https://stackoverflow.com/questions/65038206/how-to-get-indices-of-top-k-values-from-a-numpy-array/75381393#75381393
  array = np.copy (array)
  if k < len (array):
    partition = np.argpartition (array, -k) # partition around [len-k]
    not_k_indices = partition[:-k]          # k_indices = [-k:]
    array[not_k_indices] = filler
  return array
assert (top_k_filter ([9,1,3,7,5,4], 3) == [9,0,0,7,5,0]).all()

# == top_p_filter ==
# Assign `filler` to all probabilities except for the top elements exceeding cumulative probability `p`.
# This results in a distribution for "Nucleus Sampling". See: https://arxiv.org/pdf/1904.09751.pdf
def top_p_filter (probs, p, filler = 0):
  probs = np.array (probs, dtype = np.float64)
  if p >= 1.0:
    return probs
  L = len (probs)
  descending_indices = np.argsort (-probs)              # Indices for descending probabilities
  unsort_indices = np.zeros (L, dtype = int)            # Prepare to reassociate masking of sorted values
  unsort_indices[descending_indices] = np.arange (L)    # Assign indices to map back into unsorted probabilities
  cumulative_sums = np.cumsum (probs[descending_indices])
  mask_below_p = cumulative_sums < p                    # True for cumulative probs, one short of reaching p
  mask_above_p = np.roll (mask_below_p, +1)             # Shift by one to include probability to exceed p
  mask_above_p[0] = p > 0                               # Fix up first field that became False due to roll
  array_mask = mask_above_p[unsort_indices]             # Reorder mask to apply to unsorted array
  probs[~array_mask] = filler                           # Reset unwanted logits with filler
  return probs
assert (top_p_filter ([.2, 0, .1, .4, .3, 0], 0.75) == [0.2, 0, 0, 0.4, 0.3, 0.0]).all()

# == penalty_decay ==
# Calculate decay, so repeat_penalty becomes 1.0 after penalty_steps.
def penalty_decay (repeat_penalty, penalty_steps):
  decay = (1.0 / repeat_penalty) ** (1.0 / penalty_steps)
  return decay

# == sample_probabilities ==
# Sample from a probability distribution with variable temperature and repetittion penalty.
def sample_probabilities (probs, temp = 1.0, last_tokens = [], repeat_penalty = 1.2, penalty_steps = 8):
  probs = np.array (probs, dtype = np.float64)
  decay = penalty_decay (repeat_penalty, penalty_steps)
  for t in reversed (last_tokens):
    if repeat_penalty <= 1.0: break
    probs[t] /= repeat_penalty
    repeat_penalty *= decay
  if temp != 1.0:
    dist = np.exp (np.log (probs) / temp)
  else:
    dist = probs
  dist /= np.sum (dist)
  sample = np.argmax (np.random.multinomial (1, dist))
  return sample

# == sample_greedy ==
# Greedy sampling from a probability distribution with repetittion penalty.
def sample_greedy (probs, last_tokens = [], repeat_penalty = 1, penalty_steps = 8):
  probs = np.array (probs, dtype = np.float64)
  decay = penalty_decay (repeat_penalty, penalty_steps)
  for t in reversed (last_tokens):
    if repeat_penalty <= 1.0: break
    probs[t] /= repeat_penalty
    repeat_penalty *= decay
  # probs /= np.sum (probs)             # normalization is not needed for argmax
  sample = np.argmax (probs)
  return sample
