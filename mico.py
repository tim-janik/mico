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

# == CONFIG ==
CONFIG = util.Bunch (
  dump = "",
  extension = [],
  collect = [],
  verbose = 0,
  parse_collected = False,
  reduce_polypony = False,
  contiguous_notes = False,
  transpose_to_c = False,
)

# == parse_options ==
def _parse_options ():
  p = argparse.ArgumentParser (description = __doc__)
  a = p.add_argument
  a ('--collect', default = CONFIG.collect, action = 'append', help = "Collect files recursively")
  a ('--dump', type = str, default = CONFIG.dump, help = "Dump MIDI file events")
  a ('--parse-collected', default = CONFIG.parse_collected, action = 'store_true', help = "Dump collected files")
  a ('--reduce-polypony', default = CONFIG.reduce_polypony, action = 'store_true', help = "Dump collected files")
  a ('--contiguous-notes', default = CONFIG.contiguous_notes, action = 'store_true', help = "Dump collected files")
  a ('--transpose-to-c', default = CONFIG.transpose_to_c, action = 'store_true', help = "Dump collected files")
  a ('--extension', default = CONFIG.extension, action = 'append', help = "Only collect files matching extension")
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
  def monophonic_notes (self):
    return MidiTune ('', pmidi.reduce_polypony (self.notes))
  def contiguous_notes (self, min_duration = 1 / 8, max_duration = 99e99):
    return MidiTune ('', pmidi.contiguous_notes (self.notes, min_duration, max_duration))
  def reduce_polypony (self):
    return MidiTune ('', pmidi.reduce_polypony (self.notes))
  def transpose_to_c (self):
    return MidiTune ('', pmidi.transpose_to_c (self.notes))

# == parse_midis ==
# Parse and yield a MidiTune object for one or many MIDI files.
def parse_midi (filenames):
  for filename in util.as_list (filenames):
    try:
      mfile = mido.MidiFile (filename, clip = True)
    except Exception as ex:
      print (f'{filename}: error:', repr (ex), file = sys.stderr)
      continue
    iset, xset = [], []
    notes, attrs = pmidi.analyze_midi (mfile, iset, xset, dedup = False, verbose = CONFIG.verbose)
    tune = MidiTune (filename, notes, attrs)
    yield tune

# == collect ==
# Collect files recursively under `root`, filtered by matching `extension`.
def collect (root, extension = None):
  return sorted (util.collect_files (root, extension))

# == main ==
def _main (argv):
  global CONFIG, midi_files, dataset_base, dataset_csv, dataset_hdf5
  CONFIG = _parse_options()
  if CONFIG.dump:
    print (mido.MidiFile (CONFIG.dump, clip = True))
    sys.exit (0)
  elif CONFIG.collect:
    collected = collect (CONFIG.collect, CONFIG.extension)
    if CONFIG.parse_collected:
      for tune in parse_midi (collected):
        print (tune.filename + ':', tune)
        if CONFIG.reduce_polypony:
          tune = tune.reduce_polypony()
        if CONFIG.contiguous_notes:
          tune = tune.contiguous_notes()
        if CONFIG.transpose_to_c:
          tune = tune.transpose_to_c()
        if tune.notes.any():
          print (tune.notes)
    else:
      print ('\n'.join (collected))
    sys.exit (0)
  print (__doc__)
  sys.exit (0)
if __name__ == "__main__":
  _main (sys.argv)
