##############################
Siglent SDG Base / Channel
##############################

Shared base class and per-channel API for the Siglent SDG family of
function/arbitrary waveform generators. Users typically instantiate one of
the concrete model subclasses (:class:`~pymeasure.instruments.siglenttechnologies.SDG1000`,
:class:`~pymeasure.instruments.siglenttechnologies.SDG1000X`,
:class:`~pymeasure.instruments.siglenttechnologies.SDG1000XPlus`,
:class:`~pymeasure.instruments.siglenttechnologies.SDG2000X`) rather than
:class:`SDGBase` directly.

.. autoclass:: pymeasure.instruments.siglenttechnologies.siglent_sdg_base.SDGBase
    :members:
    :show-inheritance:

.. autoclass:: pymeasure.instruments.siglenttechnologies.siglent_sdg_base.SDGChannel
    :members:
    :show-inheritance:
