#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import sys, os

# == Bunch ==
class Bunch: # simplified object notation
  def __init__ (self, **kw):
    self.__dict__.update (kw)
  def __str__ (self):
    return str (vars (self))

# == collect_files ==
def collect_files (where, extension = None):
  # match extension(s)
  extensions = tuple (as_list (extension)) if extension else None
  def matches (path):
    if not extensions:
      return True
    return path.lower().endswith (extensions)
  # recurse into path(s)
  collected = []
  for path in as_list (where):
    if os.path.isdir (path):
      for dirpath, dirnames, filenames in os.walk (path):
        for filename in filenames:
          if matches (filename):
            collected.append (os.path.join (dirpath, filename))
    elif matches (path) and os.path.exists (path):
      collected.append (path)
  return collected

