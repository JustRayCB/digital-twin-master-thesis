#set page(width: 420mm, height: 90mm, margin: 8mm, fill: white)
#set text(size: 8pt)

#let blue = rgb("#2563eb")
#let muted = rgb("#4b5563")

#let photo-card(path, timestamp, note) = block(width: 68mm)[
  #rect(
    width: 68mm,
    height: 38.25mm,
    radius: 2pt,
    stroke: 0.5pt + rgb("#d1d5db"),
    inset: 0pt,
  )[
    #image(path, width: 68mm, height: 38.25mm, fit: "cover")
  ]
  #v(1.6mm)
  #align(center)[
    #text(weight: "bold", size: 8pt)[#timestamp]
    #linebreak()
    #text(fill: muted, size: 7pt)[#note]
  ]
]

#let irrigation(time) = block(width: 16mm)[
  #align(center + horizon)[
    #text(fill: blue, size: 17pt)[→]
    #v(0.5mm)
    #text(fill: blue, weight: "bold", size: 6.5pt)[AI irrigation]
    #linebreak()
    #text(weight: "bold", size: 7pt)[#time]
    #linebreak()
    #text(fill: muted, size: 6.5pt)[8 s]
  ]
]

#align(center)[
  #text(size: 14pt, weight: "bold")[Visual progression around autonomous irrigation events]
  #v(1mm)
]

#v(5mm)

#grid(
  columns: (68mm, 16mm, 68mm, 16mm, 68mm, 16mm, 68mm, 16mm, 68mm),
  align: horizon,
  photo-card(
    "data/timeline-images/01-2026-05-09T10-55-09Z.jpg",
    [9 May · 12:55],
    [Initial frame],
  ),
  irrigation([16:55]),
  photo-card(
    "data/timeline-images/02-2026-05-09T15-25-09Z.jpg",
    [9 May · 17:25],
    [30 min after action 1],
  ),
  irrigation([19:55]),
  photo-card(
    "data/timeline-images/03-2026-05-09T18-25-09Z.jpg",
    [9 May · 20:25],
    [30 min after action 2],
  ),
  irrigation([10 May · 08:55]),
  photo-card(
    "data/timeline-images/04-2026-05-10T07-25-09Z.jpg",
    [10 May · 09:25],
    [30 min after action 3],
  ),
  irrigation([11:55]),
  photo-card(
    "data/timeline-images/05-2026-05-10T10-25-09Z.jpg",
    [10 May · 12:25],
    [30 min after action 4],
  ),
)

#v(5mm)

