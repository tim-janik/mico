#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import sys

# == Bunch ==
class Bunch: # simplified object notation
  def __init__ (self, **kw):
    self.__dict__.update (kw)
  def __str__ (self):
    return str (vars (self))
