# nova/config.py
from __future__ import annotations
import os

def envflag(name: str, default: str='0') -> bool:
    return (os.getenv(name, default) or '').lower() in ('1','true','yes','on')

MODEL_DEFAULT = os.getenv('MODEL', os.getenv('NOVA_MODEL', 'nous-hermes-13b-fast:latest'))

# Web knobs
WEB_ON        = envflag('NOVA_WEB', '0')
WEB_FORCE     = envflag('NOVA_FORCE_WEB', '0')
WEB_MAXDOCS   = int(os.getenv('NOVA_WEB_MAXDOCS', '6'))
WEB_TIMEOUT_S = int(os.getenv('NOVA_WEB_TIMEOUT', '12'))

# Diagnostics
DIAG          = envflag('NOVA_DIAG', '0')
TIMINGS       = envflag('NOVA_TIMINGS', '0')

# Style toggles — accept BOTH spellings for compatibility
NO_EMOJI      = envflag('NOVA_NO_EMOJI', '0') or envflag('NOVA_NOEMOJI', '0')
