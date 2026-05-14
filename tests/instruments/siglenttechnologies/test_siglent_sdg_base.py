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

import struct

import pytest

from pymeasure.test import expected_protocol
from pymeasure.instruments.siglenttechnologies import (
    SDG1000,
    SDG1000X,
    SDG1000XPlus,
    SDG2000X,
)

# Canonical compound BSWV reply used by several tests; mirrors §3.4 of the
# SDG programming guide.
BSWV_REPLY_C1 = (
    b"C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,2V,AMPVRMS,0.707Vrms,"
    b"OFST,0V,HLEV,1V,LLEV,-1V,PHSE,0"
)


def test_init():
    """Constructor must not issue any spurious commands."""
    with expected_protocol(SDG1000X, []):
        pass


def test_idn():
    with expected_protocol(
        SDG1000X,
        [(b"*IDN?",
          b"Siglent Technologies,SDG1062X,SDG1XCAQ3R1234,1.01.01.33R1")],
    ) as inst:
        assert inst.id.startswith("Siglent Technologies,SDG1062X")


def test_reset():
    with expected_protocol(SDG1000X, [(b"*RST", None)]) as inst:
        inst.reset()


@pytest.mark.parametrize("shape", ["SINE", "SQUARE", "RAMP", "PULSE",
                                   "NOISE", "ARB", "DC"])
def test_shape_set(shape):
    with expected_protocol(
        SDG1000X,
        [(f"C1:BSWV WVTP,{shape}".encode(), None)],
    ) as inst:
        inst.ch_1.shape = shape


def test_shape_get():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV?", BSWV_REPLY_C1)],
    ) as inst:
        assert inst.ch_1.shape == "SINE"


def test_frequency_set():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV FRQ,1000", None)],
    ) as inst:
        inst.ch_1.frequency = 1000


def test_frequency_get_strips_HZ_suffix():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV?", BSWV_REPLY_C1)],
    ) as inst:
        assert inst.ch_1.frequency == 1000.0


def test_frequency_get_applies_KHZ_multiplier():
    reply = b"C1:BSWV WVTP,SINE,FRQ,2.5KHZ,AMP,2V,OFST,0V,PHSE,0"
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", reply)]) as inst:
        assert inst.ch_1.frequency == pytest.approx(2500.0)


def test_frequency_get_applies_MHZ_multiplier():
    reply = b"C1:BSWV WVTP,SINE,FRQ,10MHZ,AMP,2V,OFST,0V,PHSE,0"
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", reply)]) as inst:
        assert inst.ch_1.frequency == pytest.approx(10e6)


def test_amplitude_set():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV AMP,2", None)],
    ) as inst:
        inst.ch_1.amplitude = 2.0


def test_amplitude_get_strips_V_suffix():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV?", BSWV_REPLY_C1)],
    ) as inst:
        assert inst.ch_1.amplitude == pytest.approx(2.0)


def test_offset_get():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        assert inst.ch_1.offset == pytest.approx(0.0)


def test_voltage_high_get():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        assert inst.ch_1.voltage_high == pytest.approx(1.0)


def test_voltage_low_get():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        assert inst.ch_1.voltage_low == pytest.approx(-1.0)


def test_phase_get():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        assert inst.ch_1.phase == pytest.approx(0.0)


def test_period_get_strips_S_suffix():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        assert inst.ch_1.period == pytest.approx(0.001)


def test_period_get_applies_MS_multiplier():
    reply = b"C1:BSWV WVTP,SINE,FRQ,100HZ,PERI,10MS,AMP,2V,OFST,0V,PHSE,0"
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", reply)]) as inst:
        assert inst.ch_1.period == pytest.approx(0.010)


def test_duty_cycle_set():
    with expected_protocol(SDG1000X, [(b"C1:BSWV DUTY,50", None)]) as inst:
        inst.ch_1.duty_cycle = 50.0


def test_output_on():
    with expected_protocol(SDG1000X, [(b"C1:OUTP ON", None)]) as inst:
        inst.ch_1.output = True


def test_output_off():
    with expected_protocol(SDG1000X, [(b"C2:OUTP OFF", None)]) as inst:
        inst.ch_2.output = False


def test_output_get():
    with expected_protocol(
        SDG1000X,
        [(b"C1:OUTP?", b"C1:OUTP ON,LOAD,HZ,PLRT,NOR")],
    ) as inst:
        assert inst.ch_1.output is True


def test_output_load_hiz():
    with expected_protocol(SDG1000X, [(b"C1:OUTP LOAD,HZ", None)]) as inst:
        inst.ch_1.output_load = "HZ"


def test_output_load_50ohm():
    with expected_protocol(SDG1000X, [(b"C1:OUTP LOAD,50", None)]) as inst:
        inst.ch_1.output_load = 50


def test_output_load_get_hiz():
    with expected_protocol(
        SDG1000X,
        [(b"C1:OUTP?", b"C1:OUTP ON,LOAD,HZ,PLRT,NOR")],
    ) as inst:
        assert inst.ch_1.output_load == "HZ"


def test_output_load_get_50ohm():
    with expected_protocol(
        SDG1000X,
        [(b"C1:OUTP?", b"C1:OUTP ON,LOAD,50,PLRT,NOR")],
    ) as inst:
        assert inst.ch_1.output_load == 50


def test_output_polarity_invert():
    with expected_protocol(SDG1000X, [(b"C1:OUTP PLRT,INVT", None)]) as inst:
        inst.ch_1.output_polarity = "INVT"


def test_channel_2_routes_to_C2():
    """Verify the {ch} placeholder is replaced with the channel id."""
    with expected_protocol(SDG1000X, [(b"C2:BSWV FRQ,500", None)]) as inst:
        inst.ch_2.frequency = 500


def test_get_basic_wave_returns_dict():
    with expected_protocol(SDG1000X, [(b"C1:BSWV?", BSWV_REPLY_C1)]) as inst:
        result = inst.ch_1.get_basic_wave()
        assert result["shape"] == "SINE"
        assert result["frequency"] == pytest.approx(1000.0)
        assert result["amplitude"] == pytest.approx(2.0)
        assert result["voltage_high"] == pytest.approx(1.0)
        assert result["voltage_low"] == pytest.approx(-1.0)


def test_set_basic_wave_emits_compound_write():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV FRQ,1000,AMP,2,OFST,0.5", None)],
    ) as inst:
        inst.ch_1.set_basic_wave(frequency=1000, amplitude=2, offset=0.5)


def test_set_basic_wave_with_shape_string():
    with expected_protocol(
        SDG1000X,
        [(b"C1:BSWV WVTP,SQUARE,FRQ,1000", None)],
    ) as inst:
        inst.ch_1.set_basic_wave(shape="SQUARE", frequency=1000)


def test_set_basic_wave_unknown_key_raises():
    """No SCPI exchange — error must fire before any write hits the wire."""
    with expected_protocol(SDG1000X, []) as inst:
        with pytest.raises(ValueError):
            inst.ch_1.set_basic_wave(bogus=1)


def test_arb_select_by_name():
    with expected_protocol(
        SDG1000X,
        [(b"C1:ARWV NAME,my_wave", None)],
    ) as inst:
        inst.ch_1.arb_select_name = "my_wave"


def test_arb_select_by_index():
    with expected_protocol(
        SDG1000X,
        [(b"C1:ARWV INDEX,5", None)],
    ) as inst:
        inst.ch_1.arb_select_index = 5


def test_arb_select_index_get():
    with expected_protocol(
        SDG1000X,
        [(b"C1:ARWV?", b"C1:ARWV INDEX,2,NAME,StairUp")],
    ) as inst:
        assert inst.ch_1.arb_select_index == 2


def test_stored_waveform_list():
    with expected_protocol(
        SDG1000X,
        [(b"STL?",
          b"STL M0,sine,M1,noise,M2,stairup,M3,EMPTY,M4,user_wave")],
    ) as inst:
        result = inst.stored_waveform_list
        assert (0, "sine") in result
        assert (1, "noise") in result
        assert (2, "stairup") in result
        assert (4, "user_wave") in result
        # EMPTY slots are filtered out.
        assert not any(slot == "EMPTY" for _, slot in result)


def test_arb_indices():
    """Convenience helper returns just the indices from stored_waveform_list."""
    with expected_protocol(
        SDG1000X,
        [(b"STL?", b"STL M2,stairup,M3,stairdn,M10,expfal")],
    ) as inst:
        assert inst.arb_indices() == [2, 3, 10]


def test_arb_names():
    """Convenience helper returns just the names from stored_waveform_list."""
    with expected_protocol(
        SDG1000X,
        [(b"STL?", b"STL M2,stairup,M3,stairdn,M10,expfal")],
    ) as inst:
        assert inst.arb_names() == ["stairup", "stairdn", "expfal"]


def test_screen_save_time():
    with expected_protocol(
        SDG1000X,
        [(b"SCSV 5", None)],
    ) as inst:
        inst.screen_save_time = "5"


def test_data_arb_upload_16bit():
    """Verify the 16-bit upload framing: minimal ASCII header + LE int16.

    The driver uses :meth:`pyvisa.Adapter.write_binary_values` with
    ``header_fmt="empty"`` to append the raw int16 little-endian payload
    after ``WAVEDATA,`` (matches §3.32 Example 2 of the programming
    guide); USBTMC EOM handles message framing so no trailing newline
    is sent.
    """
    samples = [0x1000, 0x2000, -0x1000, 0x7FFF]
    payload = struct.pack(f"<{len(samples)}h", *samples)
    expected_bytes = b"C1:WVDT WVNM,test_wave,WAVEDATA," + payload
    with expected_protocol(
        SDG1000XPlus,
        [(expected_bytes, None)],
    ) as inst:
        inst.ch_1.data_arb("test_wave", samples)


def test_data_arb_upload_14bit_left_shifts():
    """On a 14-bit model, samples are left-shifted by 2 before transmission."""
    samples = [0x100, -0x100, 0x1FFF]
    shifted = [s << 2 for s in samples]
    payload = struct.pack(f"<{len(samples)}h", *shifted)
    expected_bytes = b"C2:WVDT WVNM,foo,WAVEDATA," + payload
    with expected_protocol(
        SDG1000X,
        [(expected_bytes, None)],
    ) as inst:
        inst.ch_2.data_arb("foo", samples)


def test_data_arb_too_long_raises():
    with expected_protocol(SDG1000X, []) as inst:
        too_many = [0] * (inst._max_arb_points + 1)
        with pytest.raises(ValueError):
            inst.ch_1.data_arb("oops", too_many)


def test_data_arb_sample_out_of_range_raises():
    with expected_protocol(SDG1000X, []) as inst:
        # SDG1000X is 14-bit; valid range is [-8192, 8191].
        with pytest.raises(ValueError):
            inst.ch_1.data_arb("oops", [0x4000])


def test_sdg2000x_frequency_validator_allows_120MHz():
    """SDG2000X spec extends to 120 MHz — must not raise."""
    with expected_protocol(
        SDG2000X,
        [(b"C1:BSWV FRQ,1.2e+08", None)],
    ) as inst:
        inst.ch_1.frequency = 120e6


def test_sdg1000x_frequency_validator_rejects_above_60MHz():
    """SDG1000X tops out at 60 MHz; a higher value must raise."""
    with expected_protocol(SDG1000X, []) as inst:
        with pytest.raises(ValueError):
            inst.ch_1.frequency = 100e6


def test_sdg1000_frequency_validator_allows_up_to_50MHz():
    with expected_protocol(
        SDG1000,
        [(b"C1:BSWV FRQ,5e+07", None)],
    ) as inst:
        inst.ch_1.frequency = 50e6
