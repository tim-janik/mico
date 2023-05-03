#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0

"""
Usage: mico.py [--dump midifile]
"""

# == imports ==
import sys, argparse, os, re
import mido
from util import Bunch

# == CONFIG ==
CONFIG = Bunch (
  dump = "",
  verbose = 0,
)

# == parse_options ==
def parse_options ():
  p = argparse.ArgumentParser (description = __doc__)
  a = p.add_argument
  a ('--dump', type = str, default = CONFIG.dump, help = "Dump MIDI file events")
  a ('-v', '--verbose', default = CONFIG.verbose, action = 'store_true', dest = 'verbose',
     help = "Increase output messages or debugging info")
  return p.parse_args()

# == main ==
def _main (argv):
  global CONFIG, midi_files, dataset_base, dataset_csv, dataset_hdf5
  CONFIG = parse_options()
  if CONFIG.dump:
    print (mido.MidiFile (CONFIG.dump, clip = True))
    sys.exit (0)
  print (__doc__)
  sys.exit (0)
if __name__ == "__main__":
  _main (sys.argv)
