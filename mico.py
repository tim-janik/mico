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
from pmidi import pitch_name, gm_instrument_name, tune_stats, plot_pitch_hist, plot_semitone_hist, play_notes, create_midifile

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
krumhansl_major_key_weights = krumhansl_major_key_weights / np.sum (krumhansl_major_key_weights)

# == random_midi ==
def random_midi (randmidi):
  tune, last_tokens, next_step = [], [], 0
  N = 10000
  for i in range (N):
    probs = krumhansl_major_key_weights
    # probs = top_p_filter (probs, 0.7)
    semitone = sample_probabilities (probs, temp = 0.1, last_tokens = last_tokens)
    last_tokens.append (semitone)
    octave = 1 + sample_probabilities (softmax ([ 1, 1, 1, 1, 1, 1, 1, 1 ]), temp = 1.0)
    duration = 0.27
    midipitch = octave * 12 + semitone
    note = [ midipitch, duration, next_step ]
    tune.append (note)
    next_step = duration
  create_midifile (randmidi, tune, 120)
  print (["%.2f" % v for v in np.histogram (last_tokens, bins = 12, range = (0, 12))[0]])

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
