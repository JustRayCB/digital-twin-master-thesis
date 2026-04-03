from turtle import xcor

import requests

url = "http://192.168.0.17/snapshot"

# Define your desired settings here
# Available framesizes: 96X96, QQVGA, QCIF, HQVGA, 240X240, QVGA, CIF,
# HVGA, VGA, SVGA, XGA, HD, SXGA, UXGA
# Quality: 10 to 63 (lower is sharper/larger file size)
params = {"framesize": "VGA", "quality": 80}

print(f"Requesting snapshot with params: {params}...")

r = requests.get(url, params=params, timeout=(30, 60))
r.raise_for_status()

with open("snapshot.jpg", "wb") as f:
    f.write(r.content)

print("saved snapshot.jpg successfully")
