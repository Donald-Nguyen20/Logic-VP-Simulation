# -*- coding: utf-8 -*-
"""Core logic cua T-Designer Lite (khong phu thuoc GUI)."""
from .model import (
    Circuit, Block, Connection, Simulator, DefGenerator,
    BLOCK_SPECS, BLOCK_ORDER, spec,
)
from .importer import parse_def_text, def_to_circuit, read_pdf
