#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kot karelajı - hızlı başlatıcı
==============================

Paketi kurmadan, doğrudan bu klasörden çalıştırmak için::

    python karelaj.py uret --sinir 40.7530,29.9301,40.7602,29.9443 --aralik 25
    python karelaj.py arayuz

``python -m karelaj ...`` ile tamamen aynı işi yapar.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from karelaj.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
