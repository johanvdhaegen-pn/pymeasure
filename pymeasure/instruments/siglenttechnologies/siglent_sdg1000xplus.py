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

from .siglent_sdg_base import SDGBase


class SDG1000XPlus(SDGBase):
    """Driver for the Siglent SDG1000X Plus series function/arbitrary waveform generator.

    Two channels, 16-bit DAC, 1 GSa/s sampling, 8 Mpts of arbitrary waveform
    memory per channel. The series covers:

    * SDG1022X Plus (25 MHz sine)
    * SDG1032X Plus (30 MHz sine)
    * SDG1062X Plus (60 MHz sine)

    PRBS, multi-pulse, sequence playback and the built-in web server are
    supported by the instrument but not yet exposed by this driver — the
    MVP focuses on basic-waveform / arbitrary-waveform output.
    """

    _max_frequency_sine = 60e6
    _arb_resolution_bits = 16
    _max_arb_points = 8_000_000

    def __init__(self, adapter, name="Siglent SDG1000X Plus", **kwargs):
        super().__init__(adapter, name, **kwargs)
