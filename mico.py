#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0

"""
Find and process MIDI files.
"""

# == imports ==
import sys, argparse, os, re
import mido
import util

# == CONFIG ==
CONFIG = util.Bunch (
  dump = "",
  extension = [],
  collect = [],
  verbose = 0,
)

# == collect ==
# Collect files recursively under `root`, filtered by matching `extension`.
def collect (root, extension = None):
  return sorted (util.collect_files (root, extension))

# == parse_options ==
def _parse_options ():
  p = argparse.ArgumentParser (description = __doc__)
  a = p.add_argument
  a ('--dump', type = str, default = CONFIG.dump, help = "Dump MIDI file events")
  a ('--collect', default = CONFIG.collect, action = 'append', help = "Collect files recursively")
  a ('--extension', default = CONFIG.extension, action = 'append', help = "Only collect files matching extension")
  a ('-v', '--verbose', default = CONFIG.verbose, action = 'store_true', dest = 'verbose',
     help = "Increase output messages or debugging info")
  return p.parse_args()

# == main ==
def _main (argv):
  global CONFIG, midi_files, dataset_base, dataset_csv, dataset_hdf5
  CONFIG = _parse_options()
  if CONFIG.dump:
    print (mido.MidiFile (CONFIG.dump, clip = True))
    sys.exit (0)
  elif CONFIG.collect:
    print ('\n'.join (collect (CONFIG.collect, CONFIG.extension)))
    sys.exit (0)
  print (__doc__)
  sys.exit (0)
if __name__ == "__main__":
  _main (sys.argv)
