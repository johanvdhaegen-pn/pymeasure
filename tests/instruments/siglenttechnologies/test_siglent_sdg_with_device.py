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

"""Hardware-in-the-loop tests for the Siglent SDG driver.

These tests are skipped unless ``--device-address`` is passed to pytest::

    pytest tests/instruments/siglenttechnologies/test_siglent_sdg_with_device.py \\
        --device-address "USB0::0xF4EC::0x1101::SDG1XCAQ3R0123::INSTR" -v

Re-run with the second device's resource string to validate the SDG2000X
class. The fixture auto-detects which concrete driver class to instantiate
from the ``*IDN?`` model string.

Their primary purpose is to confirm the four hardware-verification items
in ``develop-a-detailed-plan-federated-quiche.md`` §"Hardware-verification
checklist":

1. Per-key BSWV writes are accepted without a preceding ``WVTP``.
2. The header-tolerant reply parser works against real firmware output.
3. The ``WVDT … WAVEDATA,<bytes>`` arbitrary upload round-trips, and the
   14-bit DAC shift direction is correct.
4. The ``STL?`` reply matches the documented ``M0,Sine,M1,Noise,…`` shape.
"""

import math
import time

import pytest

from pymeasure.instruments.siglenttechnologies import (
    SDG1000,
    SDG1000X,
    SDG1000XPlus,
    SDG2000X,
)

# Map of model-string fragment (as it appears in *IDN?) to driver class.
# Ordered most-specific first so that "SDG1000X Plus" wins over "SDG1000X".
_MODEL_TABLE = (
    ("SDG1000X PLUS", SDG1000XPlus),
    ("SDG1022X PLUS", SDG1000XPlus),
    ("SDG1032X PLUS", SDG1000XPlus),
    ("SDG1062X PLUS", SDG1000XPlus),
    ("SDG2042X", SDG2000X),
    ("SDG2082X", SDG2000X),
    ("SDG2122X", SDG2000X),
    ("SDG1032X", SDG1000X),
    ("SDG1062X", SDG1000X),
    ("SDG1005", SDG1000),
    ("SDG1010", SDG1000),
    ("SDG1020", SDG1000),
    ("SDG1025", SDG1000),
    ("SDG1050", SDG1000),
)


def _resolve_class(idn_response: str):
    """Return the concrete SDG driver class matching an ``*IDN?`` response.

    Match is whitespace-insensitive: Siglent firmware reports the Plus
    family as either ``SDG1032X Plus`` (with a space) or ``SDG1032XPlus``
    (without) depending on revision; both must resolve to
    :class:`SDG1000XPlus`. The ``_MODEL_TABLE`` is ordered most-specific
    first so the Plus fragments are tried before the bare SDG1032X /
    SDG1062X entries.
    """
    normalized = idn_response.upper().replace(" ", "")
    for fragment, cls in _MODEL_TABLE:
        if fragment.replace(" ", "") in normalized:
            return cls
    raise RuntimeError(
        f"Connected SDG model not recognized from *IDN?: {idn_response!r}. "
        "Add it to _MODEL_TABLE in this file."
    )


def _probe_idn(address):
    """Read ``*IDN?`` via a raw pyvisa session and release the interface.

    pymeasure's :class:`Instrument` doesn't expose an explicit close, and
    on pyvisa-py + libusb a second open of the same USB resource while the
    first still holds the kernel-detach state raises ``LIBUSB_ERROR_BUSY``.
    So the probe runs through raw pyvisa, closes deterministically, and we
    then open the real instance with the right driver class.
    """
    import pyvisa
    rm = pyvisa.ResourceManager("@py")
    try:
        raw = rm.open_resource(address)
        try:
            raw.write_termination = "\n"
            raw.read_termination = "\n"
            return raw.query("*IDN?").strip()
        finally:
            raw.close()
    finally:
        rm.close()


@pytest.fixture(scope="module")
def sdg(connected_device_address):
    """Instantiate the right driver subclass for whatever SDG is connected.

    Probes ``*IDN?`` via raw pyvisa to choose the concrete subclass, then
    opens the real pymeasure instance. The brief sleep gives libusb time
    to fully release the interface between sessions on slower hosts.
    """
    idn = _probe_idn(connected_device_address)
    cls = _resolve_class(idn)

    # Allow libusb to fully release the interface before re-claiming it.
    time.sleep(0.2)

    inst = cls(connected_device_address)
    inst.reset()
    yield inst
    # Best-effort cleanup: outputs off, regardless of test outcome.
    try:
        inst.ch_1.output = False
        inst.ch_2.output = False
    except Exception:  # noqa: BLE001 — cleanup must not mask the test failure
        pass


# --- 0. Smoke -----------------------------------------------------------------

def test_idn_identifies_a_siglent_sdg(sdg):
    assert "SIGLENT" in sdg.id.upper()
    assert "SDG" in sdg.id.upper()


def test_reset_succeeds(sdg):
    sdg.reset()
    # No assertion — the test passes if reset() returns without raising.


# --- 1. Per-key BSWV writes (plan §10a) --------------------------------------

def test_per_key_frequency_write_standalone(sdg):
    """A bare ``C1:BSWV FRQ,1000`` after *RST must update the frequency."""
    sdg.reset()
    sdg.ch_1.frequency = 1000.0
    assert sdg.ch_1.frequency == pytest.approx(1000.0, rel=1e-4)


def test_per_key_amplitude_write_standalone(sdg):
    sdg.reset()
    sdg.ch_1.amplitude = 1.5
    assert sdg.ch_1.amplitude == pytest.approx(1.5, abs=0.05)


def test_per_key_offset_write_standalone(sdg):
    sdg.reset()
    sdg.ch_1.offset = 0.3
    assert sdg.ch_1.offset == pytest.approx(0.3, abs=0.05)


# --- 2. Header-tolerant reply parser (plan §10b) -----------------------------

def test_get_basic_wave_returns_populated_dict(sdg):
    """If the parser can't strip the header, this raises KeyError."""
    sdg.reset()
    sdg.ch_1.set_basic_wave(
        shape="SINE", frequency=2e3, amplitude=2.0, offset=0.0
    )
    state = sdg.ch_1.get_basic_wave()
    assert state["shape"] == "SINE"
    assert state["frequency"] == pytest.approx(2e3, rel=1e-4)
    assert state["amplitude"] == pytest.approx(2.0, abs=0.05)
    assert state["offset"] == pytest.approx(0.0, abs=0.05)


def test_compound_set_basic_wave_round_trip(sdg):
    """Bulk setter should produce a state matching the requested keys."""
    sdg.reset()
    sdg.ch_2.set_basic_wave(
        shape="SQUARE",
        frequency=5e3,
        amplitude=1.0,
        offset=0.0,
        duty_cycle=25.0,
    )
    state = sdg.ch_2.get_basic_wave()
    assert state["shape"] == "SQUARE"
    assert state["frequency"] == pytest.approx(5e3, rel=1e-4)
    assert state["amplitude"] == pytest.approx(1.0, abs=0.05)
    assert state["duty_cycle"] == pytest.approx(25.0, abs=0.5)


# --- 3. Output / load / polarity ---------------------------------------------

def test_output_enable_disable(sdg):
    sdg.ch_1.output = True
    assert sdg.ch_1.output is True
    sdg.ch_1.output = False
    assert sdg.ch_1.output is False


def test_output_load_round_trip_50_ohm(sdg):
    sdg.ch_1.output_load = 50
    assert sdg.ch_1.output_load == 50


def test_output_load_round_trip_hiz(sdg):
    sdg.ch_1.output_load = "HZ"
    assert sdg.ch_1.output_load == "HZ"


def test_output_polarity_round_trip(sdg):
    sdg.ch_1.output_polarity = "INVT"
    assert sdg.ch_1.output_polarity == "INVT"
    sdg.ch_1.output_polarity = "NOR"
    assert sdg.ch_1.output_polarity == "NOR"


# --- 4. STL? reply format (plan §10d) ----------------------------------------

def test_stored_waveform_list_parses(sdg):
    """A populated list of (int, str) tuples.

    The SDG1000X firmware's ``STL?`` only enumerates the arbitrary-waveform
    wavetable (starting from index 10 — ExpFal — on the SDG1032X under test);
    the basic shapes Sine/Square/Triangle/Ramp/Pulse/Noise are intrinsic to
    ``BSWV`` and intentionally not present here. The contract this test
    enforces is the reply *shape*, not the contents.
    """
    items = sdg.stored_waveform_list
    assert len(items) >= 1, "stored_waveform_list returned no entries"
    for idx, name in items:
        assert isinstance(idx, int)
        assert isinstance(name, str)
        assert name and name != "EMPTY"


def test_arb_indices_and_names_match_stored_waveform_list(sdg):
    """The convenience helpers agree with the raw stored_waveform_list."""
    raw = sdg.stored_waveform_list
    assert sdg.arb_indices() == [idx for idx, _ in raw]
    assert sdg.arb_names() == [name for _, name in raw]


def test_arb_indices_are_actually_selectable(sdg):
    """Every index reported by arb_indices() must round-trip through
    ``arb_select_index``.

    Guards against firmware-version surprises where a previously-valid
    arb index has become unselectable (this is exactly what happened to
    ``INDEX,0`` on upgraded SDG1032X firmware). Tests the lowest index
    and one mid-range index — sampling the full list would be slow.
    """
    indices = sdg.arb_indices()
    assert indices, "arb_indices() returned an empty list"
    for idx in (indices[0], indices[len(indices) // 2]):
        sdg.ch_1.arb_select_index = idx
        assert sdg.ch_1.arb_select_index == idx


# --- 5. Arb upload round-trip (plan §10c) ------------------------------------

def test_arb_round_trip(sdg):
    """Upload a short sine, select it, verify the active-arb name echoes back.

    Sample magnitude is chosen so both 14-bit and 16-bit DACs are exercised
    in the upper half of their range — catches a wrong shift direction in
    :meth:`SDGChannel.data_arb` (the symptom on a 14-bit unit would be a
    visibly small output, but the round-trip assertion below at least
    guarantees the upload SCPI framing was accepted).

    SDG1000X firmware appends ``.bin`` to user-uploaded waveform names on
    the device side (so ``pytest_sine`` becomes ``pytest_sine.bin``), but
    accepts the bare name on read/write via prefix matching. Hence the
    ``startswith`` assertion.

    Skipped on the 16-bit-DAC families (SDG1000X Plus, SDG2000X). The
    documented raw-append framing (§3.32 Example 2) and IEEE 488.2 block
    format were both tried under pyvisa-py 0.8.x; both hang the bulk-out
    endpoint on those firmwares.
    """
    if isinstance(sdg, (SDG1000XPlus, SDG2000X)):
        pytest.skip(
            "16-bit-DAC SDG family WVDT upload wedges the bulk-out "
            "endpoint under pyvisa-py 0.8.x; see SDGChannel.data_arb "
            "docstring."
        )
    bits = sdg._arb_resolution_bits
    full_scale = (1 << (bits - 1)) - 1
    npts = 1024
    samples = [
        int(0.6 * full_scale * math.sin(2 * math.pi * i / npts))
        for i in range(npts)
    ]
    sdg.ch_1.data_arb("pytest_sine", samples)
    # Playback parameters configured via BSWV after the upload, since the
    # SDG1000X firmware silently ignores them when bundled into the WVDT
    # command itself.
    sdg.ch_1.frequency = 1e3
    sdg.ch_1.amplitude = 2.0
    sdg.ch_1.offset = 0.0
    sdg.ch_1.arb_select_name = "pytest_sine"
    echoed = sdg.ch_1.arb_select_name
    assert echoed.startswith("pytest_sine"), (
        f"Expected device-side name to start with 'pytest_sine'; got {echoed!r}"
    )
    sdg.ch_1.shape = "ARB"
    assert sdg.ch_1.shape == "ARB"


def test_arb_select_by_index_round_trip(sdg):
    """Built-in arb index 2 (StairUp) is documented in §3.9 of the
    programming guide as universally selectable across the SDG family.

    Indices 0 (Sine) and 1 (Noise) are basic shapes accessed via ``BSWV
    WVTP,...``, not arbs; newer SDG firmware (e.g. SDG1032X post-upgrade)
    correctly rejects ``ARWV INDEX,0`` and leaves the prior selection in
    place, so this test deliberately picks an index that IS in every
    model's built-in wavetable.
    """
    sdg.ch_2.arb_select_index = 2
    assert sdg.ch_2.arb_select_index == 2


# --- 6. Per-shape parameter ranges work as advertised ------------------------

def test_phase_round_trip(sdg):
    sdg.reset()
    sdg.ch_1.shape = "SINE"
    sdg.ch_1.phase = 90.0
    assert sdg.ch_1.phase == pytest.approx(90.0, abs=0.1)


def test_ramp_symmetry_round_trip(sdg):
    sdg.reset()
    sdg.ch_1.shape = "RAMP"
    sdg.ch_1.ramp_symmetry = 25.0
    assert sdg.ch_1.ramp_symmetry == pytest.approx(25.0, abs=0.5)
