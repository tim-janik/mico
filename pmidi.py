#!/usr/bin/env python
# This Source Code Form is licensed MPL-2.0: http://mozilla.org/MPL/2.0
import os, subprocess, tempfile
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
    assert step >= 0
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
  # collect attrs
  attrs['bpm'] = nc.bpm
  attrs['nnotes'] = nnotes
  attrs['nchords'] = nchords
  return npvec, attrs

# == count_pitches ==
def pitch_stats (tune):
  pitches = [int (pitchtuple[0]) for pitchtuple in tune]
  tc = collections.Counter (pitches)
  return tc, pitches

# == tune_stats ==
def tune_stats (tune):
  tc, pitches = pitch_stats (tune)
  note_count = len (tune)
  min_note = int (min (tc.keys()))
  max_note = int (max (tc.keys()))
  avg_note = round (0.5 * (min_note + max_note))
  occurrence = list (tc.values())
  avg_occurrence = sum (occurrence) / len (occurrence)
  min_occurrence = min (occurrence)
  max_occurrence = max (occurrence)
  semitones = np.histogram ([p % 12 for p,d,s in tune], bins = range (12 + 1))[0]
  tonica = np.argmax (semitones)
  return Bunch (note_count = note_count,
                min_note = min_note,
                max_note = max_note,
                avg_note = avg_note,
                min_occurrence = min_occurrence,
                max_occurrence = max_occurrence,
                avg_occurrence = avg_occurrence,
                tonica = tonica,
                semitones = semitones)

# == plot_pitch_hist ==
def plot_pitch_hist (splt, tune):
  tc, pitches = pitch_stats (tune)
  tstats = tune_stats (tune)
  for o in np.arange (11) * 12:
    splt.axvline (x = o, linestyle = ':', color = "#dddddd")
  splt.axhline (y = tstats.avg_occurrence, linestyle = '--', color = "#75bcfe")
  splt.axvline (x = tstats.avg_note, linestyle = '--', color = "#75bcfe")
  splt.set_xlabel ("MIDI Pitch")
  splt.set_ylabel ("Occurrence of Pitches")
  splt.hist (pitches, bins = range (128 + 1))

# == plot_semitone_hist ==
def plot_semitone_hist (splt, tune):
  semitones = [p % 12 for p,d,s in tune]
  splt.set_xlabel ("Semitones")
  splt.set_xticks (np.arange (13),
                   ("       | 0 C", "      1 C#", "     2 D", "      3 D#", "     4 E", "     5 F",
                    "      6 F#", "     7 G", "      8 G#", "     9 A", "        10 A#", "      11 B",
                    "|"))
  splt.set_ylabel ("Occurrence of Semitones")
  for o in range (12):
    color = "#333333" if o in [1, 3, 6, 8, 10] else "#dddddd"
    splt.axvline (x = o + 0.5, linestyle = ':', linewidth = 2, color = color)
  splt.hist (semitones, bins = range (12 + 1), rwidth = 0.92)

# == quantize_durations ==
def quantize_durations (durations):
  ix = np.arange (len (duration_list) - 1)                      # pair indices
  edges = 0.5 * (duration_list[ix] + duration_list[ix + 1])     # values *between* durations
  quantized_indices = np.digitize (durations, edges)
  return duration_list[quantized_indices]                       # durations quantized to duration_list
duration_list = 4 * np.array ([ 1/16, 1.5/16, 1/8, 1.5/8, 1/4, 1.5/4, 1/2, 1.5/2, 1/1])
duration_names = [ '16', '16.', '8', '8.', '4', '4.', '2', '2.', '1' ]

# == plot_duration_hist ==
def plot_duration_hist (splt, tune):
  durations = [d for p,d,s in tune]
  hist = np.histogram (durations, bins = [0] + (duration_list + 0.007).tolist())
  splt.set_xlabel ("Durations")
  splt.set_ylabel ("Occurrence of Durations")
  xs = np.arange (len (duration_list))
  splt.bar (xs, hist[0])
  splt.set_xticks (xs, duration_names)
  return hist

# == VoiceOffAllocator ==
class VoiceOffAllocator:
  def __init__ (self):
    self.chvoices = [ {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {} ] # 16
    self.pos = -1
  def tick_before_list (self, tick, flist, gap = 0):
    for offtick in flist:
      if tick <= offtick + gap:
        return True
    return False
  def check (self, channel, pitch, tick):
    chdict = self.chvoices[channel]
    allocs = chdict.get (pitch, [])
    return self.tick_before_list (tick, allocs)
  def add_offtick (self, channel, pitch, offtick, ontick, exclusive = False):
    chdict = self.chvoices[channel]
    allocs = chdict.get (pitch, None)
    if not allocs:
      chdict[pitch] = allocs = []
    multi = ontick <= offtick
    multi += self.tick_before_list (ontick, allocs)
    if multi > 1 and exclusive:
      return False
    allocs.append (offtick)
    return True
  def add_exclusive (self, channel, pitch, offtick, ontick):
    return self.add_offtick (channel, pitch, offtick, ontick, exclusive = True)
  def add_alt (self, channels, pitch, offtick, ontick):
    for channel in channels:
      if self.check (channel, pitch, ontick):
        continue
      ok = self.add_exclusive (channel, pitch, offtick, ontick)
      assert ok
      return channel
    return -1

# == create_midifile ==
def create_midifile (filename, midinotes, bpm = None, verbose = False):
  # create MIDI file, track, tempo
  mid = mido.MidiFile()
  mid.ticks_per_beat = 960
  track = mido.MidiTrack()
  mid.tracks.append (track)
  if bpm:
    track.append (mido.MetaMessage ('set_tempo', tempo = mido.bpm2tempo (bpm)))
  messages = []
  qtime = 0
  # create ON + OFF with abs time, check voice allocations
  alt_channels = [1,2,3,4,5,6,7,8, 10,11,12,13,14,15] # skip drum channel
  chvoices = VoiceOffAllocator()
  for mn in midinotes:
    vpitch, qlen, step = mn
    qtime += float (step)
    channel = 0
    pitch = round (vpitch)
    ontick = round (qtime * mid.ticks_per_beat)
    offtick = max (ontick + 1, round ((qtime + qlen) * mid.ticks_per_beat))
    ok = chvoices.add_exclusive (channel, pitch, offtick, ontick)
    if not ok:
      channel = chvoices.add_alt (alt_channels, pitch, offtick, ontick)
      if channel < 0:
        print ("Lacking voice for note:", pitch, offtick - ontick, ontick)
        channel = 0
        continue
    md = { 'channel': channel, 'note': pitch, 'type': 'note_on', 'velocity': 127, 'time': ontick }
    messages.append (md)
    md = { 'channel': channel, 'note': pitch, 'type': 'note_off', 'velocity': 0, 'time': offtick }
    messages.append (md)
    channel = 0
  # sort by tick, OFF before ON, velocity 0 first
  messages = sorted (messages, key = lambda md: (md['time'], md['type'], md['velocity']))
  # create delta times
  mtime = 0
  for md in messages:
    md['time'] -= mtime
    mtime += md['time']
  # count voice allocations
  if verbose:
    chvoices = [ {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {} ] # 16
    maxtones = 0
    for md in messages:
      ckey = md['channel']
      pkey = md['note'] # pitch
      if md['type'] == 'note_off':
        chvoices[ckey][pkey] -= 1
      if md['type'] == 'note_on':
        chvoices[ckey][pkey] = chvoices[ckey].get (pkey, 0) + 1
        maxtones = max (maxtones, chvoices[ckey][pkey])
    print (f"{filename}: max voice allocs:", maxtones)
  # turn events into mido.Message
  for md in messages:
    mtype = md['type']
    del md['type']
    track.append (mido.Message (mtype, **md))
  mid.save (filename)

# == pitch_name ==
def pitch_name (pitch, other = '.'):
  if pitch < 0 or pitch > 127:
    return other
  name = MIDI_PITCH_SEMITONE_NAMES[pitch % 12]
  name += '%u' % (pitch // 12 - 1)
  return name
MIDI_PITCH_SEMITONE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# == gm_instrument_name ==
def gm_instrument_name (i):
  return GENERAL_MIDI_LEVEL1_INSTRUMENT_PATCH_MAP[i] if i >= 0 and i <= 127 else ''

# == MIDI GM ==
# https://www.midi.org/specifications-old/item/gm-level-1-sound-set
GENERAL_MIDI_LEVEL1_INSTRUMENT_PATCH_MAP = [
  # 0
  "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavi",
  # 8
  "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
  # 16
  "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
  # 24
  "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar harmonics",
  # 32
  "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
  # 40
  "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
  # 48
  "String Ensemble 1", "String Ensemble 2", "SynthStrings 1", "SynthStrings 2", "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
  # 56
  "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2",
  # 64
  "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
  # 72
  "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
  # 80
  "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
  # 88
  "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
  # 96
  "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
  # 104
  "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
  # 112
  "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
  # 120
  "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause", "Gunshot",
]

# == monophonic_notes ==
# Reduce polyphonic notes by removing notes to retain a monophonic tune.
def monophonic_notes (origtune):
  tune = np.copy (origtune)
  i = 0                                         # position to search for polyphony
  while i < len (tune):
    e = i                                       # probe for 0-step notes following i
    while e+1 < len (tune) and tune[e+1][2] == 0:
      e += 1
    if e > i:                                   # e is last index of 0-step subsequence
      note = tune[i]                            # collapse into position i
      poly = tune[i:e+1]                        # polyphony subsequence
      for p, d, s in poly:
        note[0] = max (note[0], p)              # pick remaining pitch
        note[1] = max (note[1], d)              # pick longest duration
      tune = np.delete (tune, np.arange (i, e), axis = 0)
      tune[i,:] = note
    i += 1
  return tune

# == contiguous_notes ==
# Closely line up the notes, stripping pauses and remove Staccato.
def contiguous_notes (origtune, min_duration, max_duration):
  tune = np.copy (origtune)
  last_duration = 1
  L = len (tune)
  if L:
    tune[0][2] = 0
  for i, (p0,d,s0) in enumerate (tune):
    d = max (min_duration, min (d, max_duration))               # Constrain duration
    nxt = i + 1
    if nxt < L and d < tune[nxt][2]:
      gap = tune[nxt][2] - d
      while gap >= 4:                                           # TODO: use 3, depending on signature
        tune[nxt][2] -= 4                                       # Bring forward, removes pause (TODO:sig)
        gap = tune[nxt][2] - d
      d = tune[nxt][2]                                          # Fill duration, remove Staccato
    tune[i][1] = d
    last_duration = d
  return tune

# == transpose_to_c ==
# Transpose tune to C4 or C5, whichever is closer
def transpose_to_c (origtune):
  tune = np.copy (origtune)
  tstats = tune_stats (tune)
  if tstats.tonica > 0:
    octave = 0
    if tstats.min_note < 127 - tstats.max_note:
      octave = +12                                              # pick C5
    for i,(p,d,s) in enumerate (tune):
      pitch = p + octave - tstats.tonica                        # transpose into C4 or C5
      if pitch < 0:   pitch += 12                               # constrain to MIDI range
      if pitch > 127: pitch -= 12                               # constrain to MIDI range
      tune[i][0] = pitch
  return tune

# == pds_array ==
# Convert `tones` into a numpy.array with `(pitch, duration, step)` elements.
def pds_array (tones):
  tones = np.array (tones)
  if tones.shape[1] == 2:                                       # need to add step to note + duration
    assert 0
    tones = np.pad (tones, ((0,0),(0,1)), constant_values = 0)  # (None,2) -> (None,3)
    ld = 0
    for i,(p,d,s) in enumerate (tones):
      tones[i][2] = ld                                          # assign last duration to following step
      ld = d
  return tones

# == play_notes ==
def play_notes (notes, bpm = 120, verbose = False):
  notes = pds_array (notes)
  tmpfile = tempfile.NamedTemporaryFile (prefix = 'pmidi.', suffix = '.mid', delete = False)
  tmpfile.close()
  tmpmid = tmpfile.name
  create_midifile (tmpmid, notes, bpm, verbose)
  try:
    subprocess.run (['timidity', '-ia', tmpmid])
  finally:
    os.unlink (tmpmid)
