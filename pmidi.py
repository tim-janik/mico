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

# == filter_melody ==
def filter_melody (note):
  if note.channel == 9: # MIDI Drums are on Channel 10
    return False
  if note.program >= 112 and note.program < 120: # Drums
    return False
  # TODO: skip 96 ... 103 ?
  return True

# == notes_to_vector
def notes_to_vector (midi_notes, verbose):
  notes = []
  nnotes, nchords, prevstep = 0, 0, 0
  def add_note (mpitch, qlen, step):
    nonlocal nnotes, nchords, prevstep
    # while mpitch < minfold: mpitch += 12
    # while mpitch > maxfold: mpitch -= 12
    notes.append ((mpitch, qlen, step))
    nnotes += step != 0
    nchords += step == 0 and prevstep > 0
    prevstep = step
  ticks_per_beat = midi_notes[0].notecollection.ticks_per_beat if midi_notes else 0
  last_tick = 0
  iprograms = set()
  for nn in midi_notes:
    iprograms.add (nn.program)
    step = nn.tick - last_tick
    # assert step >= 0
    last_tick = nn.tick
    add_note (nn.pitch, nn.quarter_length (nn.duration), nn.quarter_length (step))
    if 0:
      print ('%snote' % ('' if step > 0 else '  '), nn.pitch, nn.duration,
             '[%u' % nn.program, GENERAL_MIDI_LEVEL1_INSTRUMENT_PATCH_MAP[nn.program] + ']',
             notes[-1])
  if verbose:
    for p in iprograms:
      print ("MIDI Program: Used:", p, GENERAL_MIDI_LEVEL1_INSTRUMENT_PATCH_MAP[p])
  return nnotes - nchords, nchords, np.array (notes, dtype = np.float32)

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

# == count_pitches ==
def pitch_stats (tune):
  pitches = [int (p) for p,d,s in tune]
  tc = collections.Counter (pitches)
  return tc, pitches

# == tune_stats ==
def tune_stats (tune):
  tc, pitches = pitch_stats (tune)
  min_note = int (min (tc.keys()))
  max_note = int (max (tc.keys()))
  avg_note = round (0.5 * (min_note + max_note))
  occurrence = list (tc.values())
  avg_occurrence = sum (occurrence) / len (occurrence)
  min_occurrence = min (occurrence)
  max_occurrence = max (occurrence)
  semitones = np.histogram ([p % 12 for p,d,s in tune], bins = range (12 + 1))[0]
  tonica = np.argmax (semitones)
  return Bunch (min_note = min_note,
                max_note = max_note,
                avg_note = avg_note,
                min_occurrence = min_occurrence,
                max_occurrence = max_occurrence,
                avg_occurrence = avg_occurrence,
                tonica = tonica,
                semitones = semitones)
