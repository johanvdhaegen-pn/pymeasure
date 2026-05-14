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


class SDG1000X(SDGBase):
    """Driver for the Siglent SDG1000X series function/arbitrary waveform generator.

    Two channels, 14-bit DAC, 150 MSa/s sampling, 16 kpts of arbitrary
    waveform memory. The series covers:

    * SDG1032X (30 MHz sine)
    * SDG1062X (60 MHz sine)

    The class caps the ``frequency`` validator at the highest SKU (60 MHz).
    """

    _max_frequency_sine = 60e6
    _arb_resolution_bits = 14
    _max_arb_points = 16_384

    def __init__(self, adapter, name="Siglent SDG1000X", **kwargs):
        super().__init__(adapter, name, **kwargs)
