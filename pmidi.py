#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import collections, mido
import numpy as np
from util import Bunch

# == collect notes ==
class NoteCollection:
  def __init__ (self, ticks_per_beat):
    self.midi_tempo = None
    self.ticks_per_beat = ticks_per_beat
    self.notes = []
    self.voices = {}
  @property
  def bpm (self):
    return 120 if self.midi_tempo == None else round (mido.tempo2bpm (self.midi_tempo) * 8192) / 8192
  class Note:
    def __init__ (self, notecollection, track, channel, tick, pitch, velocity, program):
      self.track = track
      self.channel = channel
      self.tick = tick
      self.pitch = pitch
      self.velocity = velocity
      self.program = program
      self.duration = -1
      self.notecollection = notecollection
    def quarter_length (self, ticks = None):
      ticks = ticks if ticks != None else self.duration
      return ticks / self.notecollection.ticks_per_beat
    def tuple (self):
      return (self.track, self.channel, self.pitch)
  def collect_track (self, track_idx, track):
    programs = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
    tick = 0
    # combine note on+off into Note()
    for msg in track:
      tick += msg.time
      # SET_TEMPO
      if msg.type == 'set_tempo' and len (self.notes) < 1:
        self.midi_tempo = msg.tempo # use last tempo before notes start
      # PROGRAM_CHANGE
      if msg.type == 'program_change':
        programs[msg.channel] = msg.program
      # NOTE_ON + NOTE_OFF
      if msg.type == 'note_on' or msg.type == 'note_off':
        nev = self.Note (self, track_idx, msg.channel, tick, msg.note, msg.velocity, programs[msg.channel])
        if msg.type == 'note_off' or msg.velocity == 0:
          # NOTE_OFF
          nprev = self.voices.get (nev.tuple(), None)
          if nprev:
            nprev.duration = nev.tick - nprev.tick
            del self.voices[nprev.tuple()]
        else:
          # NOTE_ON
          self.notes.append (nev)
          self.voices[nev.tuple()] = nev
    # prune invalid notes
    self.notes[:] = [note for note in self.notes if note.duration > 0]
  def filter_notes (self, pred):
    self.notes[:] = [note for note in self.notes if pred (note)]
  def deduplicate_notes (self, verbose):
    # detect and eliminate duplicate notes
    dups, deduped = set(), 0
    def prune (nn):
      nonlocal dups, deduped
      dkey = (nn.tick, nn.pitch, nn.duration)
      if dkey in dups:
        deduped += 1
        return True
      dups.add (dkey)
      return False
    self.notes[:] = [note for note in self.notes if not prune (note)]
    if deduped and verbose:
      print ("deduped %d notes" % deduped)

# == analyze_midi ==
def analyze_midi (mfile, iset, xset, dedup, verbose):
  iset, xset = set (iset), set (xset)
  attrs = {}
  # collect notes from MIDI stream
  nc = NoteCollection (mfile.ticks_per_beat)
  for ix, track in enumerate (mfile.tracks):
    nc.collect_track (ix, track)
  nc.filter_notes (filter_melody)
  if dedup:
    nc.deduplicate_notes (verbose = verbose)
  # filter by channel
  def filter_channel (note):
    ch = note.channel + 1
    if iset and not ch in iset:
      return False
    if xset and ch in xset:
      return False
    return True
  midi_notes = filter (filter_channel, nc.notes)
  # sort by tick, duration
  midi_notes = sorted (midi_notes, key = lambda nn: (nn.tick, nn.pitch, nn.channel, -nn.duration, nn.track))
  # create vector
  nnotes, nchords, npvec = notes_to_vector (midi_notes, verbose = verbose)
  # minmax
  notemin, notemax = 128, -1
  for nv in npvec:
    notemin = min (notemin, nv[0])
    notemax = max (notemax, nv[0])
  # collect attrs
  attrs['bpm'] = nc.bpm
  attrs['nnotes'] = nnotes
  attrs['nchords'] = nchords
  attrs['notemin'] = notemin
  attrs['notemax'] = notemax
  attrs['notespan'] = notemax - notemin + 1
  return npvec, attrs
