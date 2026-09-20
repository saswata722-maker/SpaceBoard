#!/usr/bin/env python3
"""Generate clean sky.html for SpaceBoard."""
import os, sys

BASE = r"C:\Users\saswa\OneDrive\Desktop\proj\SpaceBoard"
OUT = os.path.join(BASE, "app", "templates", "sky.html")
L = []

def a(s):
    L.append(s)
