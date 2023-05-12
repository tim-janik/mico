#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0

"""
Find and process MIDI files.
"""

# == imports ==
import sys, argparse, os, re
import numpy as np
import pmidi, mido
import util

# == pmidi.py exports ==
from pmidi import pitch_name, gm_instrument_name, tune_stats, plot_pitch_hist, plot_semitone_hist, plot_duration_hist, play_notes, create_midifile

# == npaux.py exports ==
from npaux import *

# == CONFIG ==
CONFIG = util.Bunch (
  collect = [],
  contiguous_notes = False,
  dump = "",
  extension = [],
  monophonic_notes = False,
  parse_collected = False,
  play = "",
  randmidi = "",
  transpose_to_c = False,
  verbose = 0,
)

# == parse_options ==
def _parse_options ():
  p = argparse.ArgumentParser (description = __doc__)
  a = p.add_argument
  a ('--collect', default = CONFIG.collect, action = 'append', help = "Collect files recursively")
  a ('--contiguous-notes', default = CONFIG.contiguous_notes, action = 'store_true', help = "Remove pauses and staccato")
  a ('--dump', type = str, default = CONFIG.dump, help = "Dump MIDI file events")
  a ('--extension', default = CONFIG.extension, action = 'append', help = "Only collect files matching extension")
  a ('--monophonic-notes', default = CONFIG.monophonic_notes, action = 'store_true', help = "Remove polyphonic notes (keeping the lead)")
  a ('--parse-collected', default = CONFIG.parse_collected, action = 'store_true', help = "Dump collected files")
  a ('--play', type = str, default = CONFIG.play, help = "Play a MIDI file")
  a ('--randmidi', type = str, default = CONFIG.randmidi, help = "Generate a random MIDI file")
  a ('--transpose-to-c', default = CONFIG.transpose_to_c, action = 'store_true', help = "Transpose tunes into C")
  a ('-v', '--verbose', default = CONFIG.verbose, action = 'store_true', dest = 'verbose',
     help = "Increase output messages or debugging info")
  return p.parse_args()

# == MidiTune ==
class MidiTune:
  def __init__ (self, filename, notes = [], attrs = {}):
    self.__dict__.update (attrs)
    self.filename = filename
    self.notes = np.copy (notes)
  def __str__ (self):
    s = '<MidiTune'
    for k,v in self.__dict__.items():
      if k not in ('filename', 'notes'):
        s += f' {k}={v}'
    s += ' notes.shape=' + str (self.notes.shape)
    s += '>'
    return s
  def contiguous_notes (self, min_duration = 1 / 8, max_duration = 99e99):
    return MidiTune ('', pmidi.contiguous_notes (self.notes, min_duration, max_duration))
  def monophonic_notes (self):
    return MidiTune ('', pmidi.monophonic_notes (self.notes))
  def transpose_to_c (self):
    return MidiTune ('', pmidi.transpose_to_c (self.notes))
  def quantize_durations (self):
    notes = np.copy (self.notes)
    notes[:,1] = pmidi.quantize_durations (notes[:,1])
    return MidiTune ('', notes)

# == parse_midis ==
# Parse and yield a MidiTune object for one or many MIDI files.
def parse_midi (filenames, dedup = True):
  for filename in util.as_list (filenames):
    try:
      mfile = mido.MidiFile (filename, clip = True)
    except Exception as ex:
      print (f'{filename}: error:', repr (ex), file = sys.stderr)
      continue
    iset, xset = [], []
    notes, attrs = pmidi.analyze_midi (mfile, iset, xset, dedup, verbose = CONFIG.verbose)
    tune = MidiTune (filename, notes, attrs)
    yield tune

# == collect ==
# Collect files recursively under `root`, filtered by matching `extension`.
def collect (root, extension = None):
  return sorted (util.collect_files (root, extension))

# == albrecht_weights ==
# Krumhansl, Carol L., 1990, "Cognitive Foundations of Musical Pitch", Oxford.
krumhansl_major_key_weights = [ 6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88 ]
accidental_weights = [ 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0 ]

# == random_midi ==
def random_midi (randmidi):
  tune, last_tokens, next_step = [], [], 0
  N = 10000
  # Mirostat: tau:  2.5    3    4    5
  # Top-p:    p:    0.56  0.65 0.85 0.95
  mirostat = Mirostat2 (temp = 1.0, tau = 3, repeat_penalty = 1.45, penalty_steps = 16)
  for i in range (N):
    octave_logits = [ 0.5, 0.95, 1.05, 0.9, 0.4 ]
    semitone_logits = krumhansl_major_key_weights
    # Combine ocatve and semitone logits into multi-octave probabilities
    octave_temp = np.array (octave_logits) / mirostat.temperature
    multi_probs = np.outer (softmax (octave_temp), softmax (semitone_logits)).flatten()
    # Logits are a vector of raw (non-normalized) predictions, intended as softmax input
    if 1:
      pitch = mirostat.sample (multi_probs, last_tokens = last_tokens)
    elif 0:
      pitch = sample_greedy (multi_probs, last_tokens, repeat_penalty = 1.5, penalty_steps = 48)
    elif 0:
      pitch = sample_probabilities (top_k_filter (multi_probs, 17), 1.0, last_tokens, repeat_penalty = 1.5)
    elif 0:
      pitch = sample_probabilities (top_p_filter (multi_probs, 0.9), 1.0, last_tokens, repeat_penalty = 1)
    last_tokens.append (pitch)
    octave = 3 #sample_probabilities (softmax ([ 1, 1, 1, ]), temp = 1.0)
    midipitch = octave * 12 + pitch
    duration = 0.27
    note = [ midipitch, duration, next_step ]
    tune.append (note)
    next_step = duration
  create_midifile (randmidi, tune, 120)
  print ("average_cross_entropy:", mirostat.average_cross_entropy(),
         "maximum_cross_entropy", mirostat.maximum_cross_entropy)
  print (["%7.2f" % v for v in np.histogram (np.array (last_tokens) % 12, bins = 12, range = (0, 12))[0]])
  print (["%7.2f" % (10000*v) for v in softmax (krumhansl_major_key_weights)])
  print (["%7.2f" % v for v in krumhansl_major_key_weights])

# == main ==
def _main (argv):
  global CONFIG, midi_files, dataset_base, dataset_csv, dataset_hdf5
  CONFIG.verbose = True
  CONFIG = _parse_options()
  if CONFIG.dump:
    print (mido.MidiFile (CONFIG.dump, clip = True))
  if CONFIG.play:
    miditune = list (parse_midi (CONFIG.play))[0]
    play_notes (miditune.notes, miditune.bpm, CONFIG.verbose)
  if CONFIG.randmidi:
    random_midi (CONFIG.randmidi)
  if CONFIG.collect:
    collected = collect (CONFIG.collect, CONFIG.extension)
    if CONFIG.parse_collected:
      for tune in parse_midi (collected):
        print (tune.filename + ':', tune)
        if CONFIG.monophonic_notes:
          tune = tune.monophonic_notes()
        if CONFIG.contiguous_notes:
          tune = tune.contiguous_notes()
        if CONFIG.transpose_to_c:
          tune = tune.transpose_to_c()
        if tune.notes.any():
          print (tune.notes)
    else:
      print ('\n'.join (collected))
  else:
    print (__doc__)
  sys.exit (0)
if __name__ == "__main__":
  _main (sys.argv)
