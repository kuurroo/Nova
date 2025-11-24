# nova/logging.py
from __future__ import annotations
import os
from .config import DIAG, TIMINGS

def log(msg: str):
    print(msg, flush=True)

def diag(msg: str):
    if DIAG: print(msg, flush=True)

def timing(msg: str):
    if TIMINGS: print(msg, flush=True)
