#!/usr/bin/env python3
"""Remove duplicate content from sky.html."""
import os

path = r"C:\Users\saswa\OneDrive\Desktop\proj\SpaceBoard\app\templates\sky.html"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

idx = c.find("</html>")
if idx >= 0:
    c = c[:idx+7] + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"Truncated to {len(c)} chars")

c2 = open(path).read()
print(f"Lines: {len(c2.splitlines())}")
for tag in ["</aside>", "</main>", "</body>", "</html>"]:
    print(f"{tag}: {c2.count(tag)}")
print(f"Has canvas: {'sky-canvas' in c2}")
