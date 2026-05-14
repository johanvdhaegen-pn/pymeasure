#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2026 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

"""Base classes for the Siglent SDG function/arbitrary waveform generator family.

The MVP exposes basic-waveform output (``BSWV``), output enable/load/polarity
(``OUTP``), built-in arbitrary waveform selection (``ARWV``), arbitrary
waveform upload (``WVDT``) and the stored-waveform listing (``STL``).
Modulation, sweep, burst, PRBS, IQ and sequence subsystems are deferred to
follow-up additions.

The Siglent SDG SCPI dialect departs from "standard" SCPI in three ways the
driver has to absorb:

* The channel selector is a **command prefix** (``C1:BSWV ...``), not a
  ``:SOURce1:`` subsystem. The :class:`pymeasure.instruments.Channel` ``{ch}``
  template handles this directly — no ``insert_id`` override is needed.
* A single ``BSWV`` query returns a compound key/value list
  (``C1:BSWV WVTP,SINE,FRQ,1000HZ,AMP,2V,...``). Per-key writes
  (``C1:BSWV FRQ,1000``) are accepted, so each property is implemented with
  a one-key set and a read that extracts the matching key from the compound
  reply.
* Replies are prefixed with the echoed command name on the SDG1000X /
  SDG1000X Plus / SDG2000X families (``CHDR OFF`` is only supported on the
  original SDG1000). The ``preprocess_reply`` of every compound-reply
  property strips the header prefix; it is a no-op when no prefix is
  present, so the driver is symmetric across all four model families.
"""

import logging
import re

from pymeasure.instruments import Channel, Instrument, SCPIMixin
from pymeasure.instruments.validators import (
    strict_discrete_set,
    strict_range,
    truncated_range,
)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


# Map of unit-suffix string (uppercase) -> multiplier to bring the numeric
# part into the canonical SI unit (Hz, s, V, %, deg). Covers every suffix
# documented in §3.4 of the SDG programming guide.
_UNIT_MULTIPLIER = {
    "": 1.0,
    "HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9,
    "S": 1.0, "MS": 1e-3, "US": 1e-6, "NS": 1e-9, "PS": 1e-12,
    "V": 1.0, "MV": 1e-3, "VPP": 1.0, "VRMS": 1.0,
    "DBM": 1.0,
    "%": 1.0,
    "DEG": 1.0,
}
_NUM_RE = re.compile(r"^([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)(.*)$")


def _to_float(token):
    """Convert a Siglent value token like ``"1.000HZ"`` / ``"-1V"`` / ``"50"`` to float.

    Unknown unit suffixes pass through with a multiplier of 1.
    """
    match = _NUM_RE.match(token.strip())
    if not match:
        return float(token)
    return float(match.group(1)) * _UNIT_MULTIPLIER.get(match.group(2).upper().strip(), 1.0)


def _strip_header(reply):
    """Strip the ``C1:BSWV `` / ``C1:OUTP `` header prefix from a compound reply.

    No-op when the header has already been suppressed via ``CHDR OFF``.
    """
    return reply.split(" ", 1)[-1]


def _bswv_parse(key, cast=_to_float):
    """Build a ``get_process`` that extracts one key from a ``BSWV?``-style reply.

    The reply, after :func:`_strip_header`, is a comma-separated key/value
    list (``WVTP,SINE,FRQ,1000HZ,AMP,2V,...``). Because the entire string is
    delivered to ``get_process`` (via ``maxsplit=0`` on the property), it is
    split here.
    """
    def _process(value):
        toks = value.split(",")
        # The list alternates KEY,VALUE,KEY,VALUE,...
        for i in range(0, len(toks) - 1, 2):
            if toks[i] == key:
                return cast(toks[i + 1])
        raise KeyError(f"Key {key!r} not present in BSWV reply: {value!r}")
    return _process


def _outp_parse(key, cast=str):
    """Build a ``get_process`` for ``OUTP?`` replies of the form
    ``ON,LOAD,50,PLRT,NOR``.

    The first token is the on/off state, then the list alternates KEY,VALUE.
    """
    def _process(value):
        toks = value.split(",")
        if key == "STATE":
            return cast(toks[0])
        for i in range(1, len(toks) - 1, 2):
            if toks[i] == key:
                return cast(toks[i + 1])
        raise KeyError(f"Key {key!r} not present in OUTP reply: {value!r}")
    return _process


def _arwv_parse(key, cast=str):
    """Build a ``get_process`` for ``ARWV?`` replies (``INDEX,2,NAME,StairUp``)."""
    def _process(value):
        toks = value.split(",")
        for i in range(0, len(toks) - 1, 2):
            if toks[i] == key:
                return cast(toks[i + 1])
        raise KeyError(f"Key {key!r} not present in ARWV reply: {value!r}")
    return _process


# Mapping from human-friendly bulk-helper keyword to the BSWV mnemonic.
_BSWV_KEYS = {
    "shape": "WVTP",
    "frequency": "FRQ",
    "period": "PERI",
    "amplitude": "AMP",
    "amplitude_rms": "AMPVRMS",
    "amplitude_dbm": "AMPDBM",
    "offset": "OFST",
    "voltage_high": "HLEV",
    "voltage_low": "LLEV",
    "phase": "PHSE",
    "duty_cycle": "DUTY",
    "pulse_width": "WIDTH",
    "pulse_rise": "RISE",
    "pulse_fall": "FALL",
    "pulse_delay": "DLY",
    "ramp_symmetry": "SYM",
    "stdev": "STDEV",
    "mean": "MEAN",
}


class SDGChannel(Channel):
    """A single output channel of a Siglent SDG waveform generator.

    Each channel has its own basic-waveform configuration (``BSWV``), output
    enable / load / polarity (``OUTP``), and arbitrary-waveform selection
    (``ARWV``). Properties are implemented as one-key SCPI writes; reads use
    a compound query whose reply is parsed for the requested key. For tight
    loops where every property update would mean a round-trip,
    :meth:`set_basic_wave` and :meth:`get_basic_wave` exchange the whole
    state in a single message.

    :param parent: Parent :class:`SDGBase` instrument.
    :param id: Channel identifier (``1`` or ``2``).
    """

    # --- basic waveform (BSWV) --------------------------------------------

    shape = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV WVTP,%s",
        """Control the basic waveform shape (str).

        Strictly one of ``"SINE"``, ``"SQUARE"``, ``"RAMP"``, ``"PULSE"``,
        ``"NOISE"``, ``"ARB"``, ``"DC"``.
        """,
        validator=strict_discrete_set,
        values=["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("WVTP", cast=str),
        dynamic=True,
    )

    frequency = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV FRQ,%g",
        """Control the basic-waveform frequency in Hz (float).""",
        validator=strict_range,
        values=[1e-6, 120e6],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("FRQ"),
        dynamic=True,
    )

    period = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV PERI,%g",
        """Control the basic-waveform period in seconds (float).""",
        validator=strict_range,
        values=[1e-9, 1e6],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("PERI"),
        dynamic=True,
    )

    amplitude = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV AMP,%g",
        """Control the basic-waveform peak-to-peak amplitude in Volts (float).""",
        validator=strict_range,
        values=[2e-3, 20.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("AMP"),
        dynamic=True,
    )

    amplitude_rms = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV AMPVRMS,%g",
        """Control the basic-waveform amplitude in Vrms (float).""",
        validator=strict_range,
        values=[1e-3, 10.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("AMPVRMS"),
        dynamic=True,
    )

    offset = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV OFST,%g",
        """Control the basic-waveform DC offset in Volts (float).""",
        validator=strict_range,
        values=[-10.0, 10.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("OFST"),
        dynamic=True,
    )

    voltage_high = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV HLEV,%g",
        """Control the basic-waveform high level in Volts (float).""",
        validator=strict_range,
        values=[-9.999, 10.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("HLEV"),
        dynamic=True,
    )

    voltage_low = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV LLEV,%g",
        """Control the basic-waveform low level in Volts (float).""",
        validator=strict_range,
        values=[-10.0, 9.999],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("LLEV"),
        dynamic=True,
    )

    phase = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV PHSE,%g",
        """Control the basic-waveform phase in degrees (float, 0 to 360).""",
        validator=strict_range,
        values=[0.0, 360.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("PHSE"),
        dynamic=True,
    )

    duty_cycle = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV DUTY,%g",
        """Control the square or pulse duty cycle in percent (float, 0.001 to 99.999).

        Only meaningful when ``shape`` is ``"SQUARE"`` or ``"PULSE"``.
        """,
        validator=strict_range,
        values=[0.001, 99.999],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("DUTY"),
        dynamic=True,
    )

    pulse_width = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV WIDTH,%g",
        """Control the pulse positive width in seconds (float).

        Only meaningful when ``shape`` is ``"PULSE"``.
        """,
        validator=strict_range,
        values=[1e-9, 1e6],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("WIDTH"),
        dynamic=True,
    )

    pulse_rise = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV RISE,%g",
        """Control the pulse rise time in seconds (float).""",
        validator=strict_range,
        values=[1e-9, 22.4],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("RISE"),
        dynamic=True,
    )

    pulse_fall = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV FALL,%g",
        """Control the pulse fall time in seconds (float).""",
        validator=strict_range,
        values=[1e-9, 22.4],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("FALL"),
        dynamic=True,
    )

    pulse_delay = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV DLY,%g",
        """Control the waveform delay in seconds (float).""",
        validator=strict_range,
        values=[0.0, 1e6],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("DLY"),
        dynamic=True,
    )

    ramp_symmetry = Instrument.control(
        "C{ch}:BSWV?", "C{ch}:BSWV SYM,%g",
        """Control the ramp symmetry in percent (float, 0 to 100).

        Only meaningful when ``shape`` is ``"RAMP"``.
        """,
        validator=strict_range,
        values=[0.0, 100.0],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_bswv_parse("SYM"),
        dynamic=True,
    )

    # --- output stage (OUTP) ---------------------------------------------

    output = Instrument.control(
        "C{ch}:OUTP?", "C{ch}:OUTP %s",
        """Control whether the channel output is enabled (bool).""",
        validator=strict_discrete_set,
        values={True: "ON", False: "OFF"},
        map_values=True,
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_outp_parse("STATE", cast=str),
    )

    output_polarity = Instrument.control(
        "C{ch}:OUTP?", "C{ch}:OUTP PLRT,%s",
        """Control the output polarity (str, ``"NOR"`` or ``"INVT"``).""",
        validator=strict_discrete_set,
        values=["NOR", "INVT"],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_outp_parse("PLRT", cast=str),
    )

    # --- arbitrary waveform selection (ARWV) -----------------------------

    arb_select_index = Instrument.control(
        "C{ch}:ARWV?", "C{ch}:ARWV INDEX,%d",
        """Control the active built-in arbitrary waveform by index (int, 0 to 198).

        The available index range depends on the model — refer to the
        programming guide §3.9 for the per-series table.
        """,
        validator=truncated_range,
        values=[0, 198],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_arwv_parse("INDEX", cast=int),
        dynamic=True,
    )

    arb_select_name = Instrument.control(
        "C{ch}:ARWV?", "C{ch}:ARWV NAME,%s",
        """Control the active arbitrary waveform by name (str).""",
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=_arwv_parse("NAME", cast=str),
    )

    # --- output load (separate property because of HiZ string value) -----

    @property
    def output_load(self):
        """Control the channel output load in ohms (int from 50 to 100000)
        or the string ``"HZ"`` for high-impedance.
        """
        reply = self.ask("C{ch}:OUTP?")
        token = _outp_parse("LOAD", cast=str)(_strip_header(reply.strip()))
        if token in ("HZ", "HiZ"):
            return "HZ"
        return int(token)

    @output_load.setter
    def output_load(self, value):
        if isinstance(value, str):
            if value.upper() not in ("HZ", "HIZ"):
                raise ValueError(
                    f"output_load string must be 'HZ' (high-Z); got {value!r}"
                )
            self.write("C{ch}:OUTP LOAD,HZ")
        else:
            value = int(value)
            if not (50 <= value <= 100000):
                raise ValueError(
                    f"output_load must be 50..100000 ohm or 'HZ'; got {value}"
                )
            self.write(f"C{{ch}}:OUTP LOAD,{value}")

    # --- bulk helpers ----------------------------------------------------

    def get_basic_wave(self):
        """Return the full basic-waveform configuration as a dict.

        Keys are the human-friendly names used by :meth:`set_basic_wave`
        (e.g. ``"frequency"``, ``"amplitude"``, ``"shape"``). Numeric values
        are returned as floats in canonical SI units (Hz, s, V, %, deg);
        ``"shape"`` is a string.
        """
        reply = _strip_header(self.ask("C{ch}:BSWV?").strip())
        toks = reply.split(",")
        raw = {toks[i]: toks[i + 1] for i in range(0, len(toks) - 1, 2)}
        out = {}
        reverse = {mnemonic: human for human, mnemonic in _BSWV_KEYS.items()}
        for mnemonic, value in raw.items():
            human = reverse.get(mnemonic, mnemonic.lower())
            if mnemonic == "WVTP":
                out[human] = value
            else:
                try:
                    out[human] = _to_float(value)
                except ValueError:
                    out[human] = value
        return out

    def set_basic_wave(self, **kwargs):
        """Set multiple basic-waveform parameters in a single SCPI message.

        Accepts the same keyword names as :meth:`get_basic_wave` returns.
        Unknown keywords raise ``ValueError``.

        Example::

            ch.set_basic_wave(shape="SINE", frequency=1e3, amplitude=2.0, offset=0)
        """
        if not kwargs:
            return
        parts = []
        for human, value in kwargs.items():
            if human not in _BSWV_KEYS:
                raise ValueError(
                    f"Unknown basic-wave parameter {human!r}; "
                    f"expected one of {sorted(_BSWV_KEYS)}"
                )
            mnemonic = _BSWV_KEYS[human]
            if isinstance(value, str):
                parts.append(f"{mnemonic},{value}")
            else:
                parts.append(f"{mnemonic},{value:g}")
        self.write("C{ch}:BSWV " + ",".join(parts))

    # --- arbitrary waveform upload (WVDT) --------------------------------

    def data_arb(self, name, samples):
        """Upload an arbitrary waveform to the volatile memory of this channel.

        :param name: Identifier the waveform is stored under. The device
            appends a ``.bin`` extension internally on the SDG1000X family
            (so an upload as ``"my_wave"`` is stored as ``"my_wave.bin"``);
            ``arb_select_name`` accepts either form via prefix matching.
        :param samples: Iterable of integer samples in two's-complement
            form. On 16-bit models (SDG1000X Plus, SDG2000X) the range is
            ``-32768..32767``; on 14-bit models (SDG1000, SDG1000X) the
            range is ``-8192..8191`` and the driver left-shifts samples by
            2 bits before transmission, so callers always pass values in
            the model's native resolution.

        :raises ValueError: If ``len(samples)`` exceeds the model's
            ``_max_arb_points`` or any sample falls outside the model's
            DAC range.

        After upload, set the playback frequency, amplitude, offset, and
        phase via :attr:`frequency`, :attr:`amplitude`, :attr:`offset`,
        :attr:`phase`. The documented ``FREQ/AMPL/OFST/PHASE`` metadata
        keys in the ``WVDT`` command itself are silently ignored on the
        SDG1000X firmware, so the driver omits them; setting via the
        ``BSWV`` properties is universally accepted.

        The waveform bytes are appended raw after the ``WAVEDATA,``
        marker (the format documented in §3.32 Example 2 of the
        programming guide). IEEE 488.2 block format with a ``#<N><Length>``
        prefix was tried as a portability fix but ended up storing the
        prefix as part of the waveform data on the firmwares that did
        accept it, so the documented raw-append form is used instead.
        The 16-bit-DAC firmwares (SDG1000X Plus, SDG2000X) wedge their
        USB bulk-out endpoint on multi-packet WVDT uploads under
        pyvisa-py 0.8.x regardless of framing; the hardware test for
        binary upload skips on those families.

        .. todo::
           Add a file-based upload path for the 16-bit-DAC firmwares
           that wedge on direct USBTMC binary transfer. The Siglent
           ``MMEMory:TRANsfer`` family of commands (programming guide
           §3.46) can move a waveform file from a network share
           (``net_storage/<path>``) or a USB flash drive
           (``U-disk0/<path>`` etc.) into the device's user storage,
           where ``ARWV NAME,<wave>`` then selects it — bypassing the
           direct binary-over-USB path entirely. Likely shape:
           ``data_arb_from_file(name, path, *, location="net_storage")``
           that writes the .bin to a shared location and issues the
           ``MMEMory:TRANsfer`` to pull it in.
        """
        bits = getattr(self.parent, "_arb_resolution_bits", 16)
        max_points = getattr(self.parent, "_max_arb_points", 8_000_000)
        sample_min = -(1 << (bits - 1))
        sample_max = (1 << (bits - 1)) - 1

        samples = list(samples)
        if len(samples) > max_points:
            raise ValueError(
                f"Arbitrary waveform has {len(samples)} samples, "
                f"exceeds the device limit of {max_points}."
            )
        for sample in samples:
            if not (sample_min <= sample <= sample_max):
                raise ValueError(
                    f"Sample {sample} outside {bits}-bit range "
                    f"[{sample_min}, {sample_max}]."
                )

        # 14-bit devices expect the 14-bit sample in the upper bits of the
        # 16-bit word that travels on the wire.
        shift = 16 - bits
        if shift:
            samples = [s << shift for s in samples]

        # header_fmt="empty" → no IEEE/HP prefix bytes, just the
        # samples-as-LE-int16 appended raw to the command. Matches the
        # programming guide §3.32 Example 2 framing exactly.
        self.write_binary_values(
            f"C{{ch}}:WVDT WVNM,{name},WAVEDATA,",
            samples,
            datatype="h",
            is_big_endian=False,
            header_fmt="empty",
        )


class SDGBase(SCPIMixin, Instrument):
    """Base class for the Siglent SDG (function/arbitrary waveform generator) family.

    Concrete model subclasses configure per-family spec limits via class
    attributes:

    * ``_max_frequency_sine`` — maximum sine-wave frequency in Hz; used to
      tighten the :attr:`SDGChannel.frequency` validator.
    * ``_arb_resolution_bits`` — DAC resolution (14 or 16).
    * ``_max_arb_points`` — maximum arbitrary waveform length.

    Users instantiate a concrete subclass (:class:`SDG1000`, :class:`SDG1000X`,
    :class:`SDG1000XPlus`, :class:`SDG2000X`) rather than this base.
    """

    # Concrete subclasses override these.
    _max_frequency_sine = 60e6
    _arb_resolution_bits = 16
    _max_arb_points = 8_000_000

    ch_1 = Instrument.ChannelCreator(SDGChannel, 1)
    ch_2 = Instrument.ChannelCreator(SDGChannel, 2)

    def __init__(self, adapter, name="Siglent SDG generator", **kwargs):
        super().__init__(
            adapter,
            name,
            usb=dict(write_termination="\n", read_termination="\n"),
            tcpip=dict(write_termination="\n", read_termination="\n"),
            **kwargs,
        )
        # Tighten the per-channel frequency validator to the model's spec.
        for ch in (self.ch_1, self.ch_2):
            ch.frequency_values = [1e-6, self._max_frequency_sine]

    stored_waveform_list = Instrument.measurement(
        "STL?",
        """Get the list of built-in waveforms stored on the instrument.

        The reply is parsed into a list of ``(index, name)`` tuples. Index
        labels (``M0``, ``M1``, ...) appear as integers; empty slots
        (``EMPTY``) are skipped.

        The set of indices reported depends on firmware revision. On the
        SDG1000X firmware the basic shapes (Sine, Noise, …) are *not*
        enumerated here — they are accessed via ``BSWV WVTP,…`` rather
        than ``ARWV`` — so the returned list typically starts at index 2
        (StairUp) or higher. Use :meth:`arb_indices` and
        :meth:`arb_names` for convenience accessors.
        """,
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=lambda v: _parse_stl(v),
    )

    def arb_indices(self):
        """Return the built-in arb indices that can be passed to
        ``arb_select_index`` on the current firmware.

        Convenience wrapper around :attr:`stored_waveform_list` that
        avoids having to guess whether a particular index is valid —
        e.g. SDG1000X firmware revisions differ on whether ``INDEX,0``
        (Sine) is accepted. Callers should pick from the returned list
        rather than hard-coding indices.
        """
        return [idx for idx, _ in self.stored_waveform_list]

    def arb_names(self):
        """Return the built-in arb names that can be passed to
        ``arb_select_name`` on the current firmware.
        """
        return [name for _, name in self.stored_waveform_list]

    # ``STL? USER`` (§3.31 of the programming guide) is intentionally not
    # exposed: the SDG1032X firmware was observed to never reply to it
    # and pyvisa-py's USB transport offers no portable way to recover
    # the read buffer once a query has timed out (``Resource.clear()``
    # raises ``VI_ERROR_NSUP_OPER``, ``flush_read_buffer`` is ASRL-only).
    # Calling the query therefore poisons every subsequent read in the
    # session. Users who need a list of user-uploaded waveforms should
    # query ``STL? USER`` themselves on a model where it is known to
    # work and handle their own timeout recovery.

    screen_save_time = Instrument.control(
        "SCSV?", "SCSV %s",
        """Control the screen-saver activation time in minutes (str).

        Accepts ``"OFF"`` or one of ``"1"``, ``"5"``, ``"15"``, ``"30"``,
        ``"60"``, ``"120"``, ``"300"``. The instrument echoes the value
        with a ``"MIN"`` suffix on read; this property returns the bare
        token.
        """,
        validator=strict_discrete_set,
        values=["OFF", "1", "5", "15", "30", "60", "120", "300"],
        preprocess_reply=_strip_header,
        maxsplit=0,
        cast=str,
        get_process=lambda v: v.rstrip("MIN").rstrip(),
    )


def _parse_stl(reply):
    """Parse a ``STL?`` reply into a list of ``(index, name)`` tuples.

    The reply has the form ``M0,Sine,M1,Noise,...``. ``EMPTY`` slots are
    omitted from the returned list.
    """
    toks = reply.split(",")
    result = []
    for i in range(0, len(toks) - 1, 2):
        label, name = toks[i].strip(), toks[i + 1].strip()
        if not label.startswith("M") or name == "EMPTY":
            continue
        try:
            idx = int(label[1:])
        except ValueError:
            continue
        result.append((idx, name))
    return result
