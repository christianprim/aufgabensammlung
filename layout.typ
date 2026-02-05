#import "@preview/unify:0.7.1": num, qty, unit, add-unit
#import "@preview/cetz:0.4.2" as cetz
#import "@preview/cetz-plot:0.1.3" as cetz-plot
#import "@preview/zap:0.5.0" as zap
#import "@preview/itemize:0.2.0" as el
#import "@preview/physica:0.9.8" as physica

#let in-list-depth = state("in-list-depth", 0)

#let prüfung(art: "Prüfung", klasse: "", datum: "", doc) = {

  set page(
    paper: "a4",
    margin: (x: 2cm, top: 2cm, bottom: 1.5cm),
    header: context {
      let page_nr = counter(page).get().first()
      if page_nr == 1 {
        place(dx: -1cm, dy: 1cm)[
          #rect(height: 1.2cm, width: 19cm, stroke: aqua + .5pt, radius: .5cm)[
            #align(horizon)[
              #text(font: "TeX Gyre Heros", fill: blue)[
                #h(.6cm) _#art #klasse vom #datum #h(1fr) Name: #h(6cm) P: #h(1cm) N: #h(1.25cm) _
              ]
            ]
          ]
        ] 
      }
    },
    
    footer: context {
      let page_nr = counter(page).get().first()
      set text(font: "TeX Gyre Heros", fill: blue)
      if calc.odd(page_nr) {
        [_KZN #h(1fr) #page_nr _]
      } else {
        [_#page_nr #h(1fr) KZN_]
      }
    }
  )
    
  set text(
    font: "TeX Gyre Pagella", 
    lang: "de",
    region: "CH"
  )

  set par(
    justify: true
  )
  set heading(numbering: "1.")
  set enum(numbering: "a)")
  
  show heading: it => text(font: "TeX Gyre Heros", fill: blue.darken(50%))[#emph[#it]]
  show heading.where(level: 1): it => text(size: 12pt)[#it]
  show math.equation: set text(font: "TeX Gyre Pagella Math")
  
  let in-list-depth = state("in-list-depth", 0)

  show enum: it => {
    in-list-depth.update(d => d + 1)
    it
    in-list-depth.update(d => d - 1)
  }
  add-unit("Lichtjahr", "LJ", "upright(\"LJ\")")
  add-unit("Lichtsekunde", "Ls", "upright(\"Ls\")")
  add-unit("Zoll", "Zoll", "upright(\"Zoll\")")
  add-unit("Umdrehung", "U", "upright(\"U\")")
  add-unit("mm Quecksilbersäule", "mmHg", "upright(\"mmHg\")")
  add-unit("Dioptrie", "dpt", "upright(\"dpt\")")
  add-unit("Umdrehungen", "U", "upright(\"U\")")

  v(1cm)
  doc
}

#let musterlösung(art: "Prüfung", klasse: "", datum: "", doc) = {

  set page(
    paper: "a4",
    margin: (x: 2cm, y: 2cm),
    header: [ 
      #text(font: "TeX Gyre Heros", fill: gray)[
           _Musterlösung zur #art der Klasse #klasse vom #datum _
        ]   
      ],
    
    footer: context {
      let page_nr = counter(page).get().first()
      set text(font: "TeX Gyre Heros", fill: gray)
      if calc.odd(page_nr) {
        [_KZN #h(1fr) #page_nr _]
      } else {
        [_#page_nr #h(1fr) KZN_]
      }
    }
  )
    
  set text(
    font: "TeX Gyre Pagella", 
    lang: "de",
    region: "CH"
  )

  set par(
    justify: true
  )

  set heading(numbering: "1.")
  set enum(numbering: "a)")
  show heading: it => text(font: "TeX Gyre Heros")[#emph[#it]]
  show heading.where(level: 1): it => text(size: 12pt)[#it]
  show math.equation: set text(font: "TeX Gyre Pagella Math")
  show: el.default-enum-list

  add-unit("Lichtjahr", "LJ", "upright(\"LJ\")")
  add-unit("Lichtsekunde", "Ls", "upright(\"Ls\")")
  add-unit("Zoll", "Zoll", "upright(\"Zoll\")")
  add-unit("Umdrehung", "U", "upright(\"U\")")
  add-unit("mm Quecksilbersäule", "mmHg", "upright(\"mmHg\")")
  add-unit("Dioptrie", "dpt", "upright(\"dpt\")")
  add-unit("Umdrehungen", "U", "upright(\"U\")")

  doc
}

// Schreibpapier
#let schreibpapier(height: none, size: 4mm) = context { 
  let grid_height = height
  if height != none {
    assert(type(height) == length, message: "Height muss eine Länge sein (z.B. 10pt)")
  } else {
    grid_height = 1fr
  }
  
  block(height: grid_height, layout(place => { 
    let columns = calc.floor(place.width / size)
    let rows = calc.floor(place.height / size)
  
    grid(
      columns: (size,) * columns,
      rows: (size,) * rows,
      stroke: aqua.lighten(20%) + .2pt,
    )
  }))
}

// Punktzahl
#let p(punktzahl) = context {
  let depth = in-list-depth.get()
  let is-right-side = calc.odd(here().page())
  let gutter = if is-right-side { 1cm } else { -1cm }
  if depth > 0 and not is-right-side { gutter -= depth * 1.5em}
  let alignment = if is-right-side { right } else { left }
  place(alignment, dx: gutter )[
    #set text(weight: "bold", fill: blue)
    #punktzahl P
  ]
}

// Farben
#let brown = rgb("#a52a2a")
#let beige = rgb("#cfb997")

// eigene Komponenten für Zap
#let lamp(name, node, ..params) = {

  let draw(ctx, position, style) = {
    zap.interface((-style.radius, -style.radius), (style.radius, style.radius), io: position.len() < 2)
    cetz.draw.circle((0, 0), radius: style.radius, ..style)
    cetz.draw.line((135deg, style.radius), (-45deg, style.radius), ..style)
    cetz.draw.line((45deg, style.radius), (-135deg, style.radius), ..style)
  }

  // Component call
  zap.component("lamp", name, node, draw: draw, ..params)
}

#let battery(name, node, ..params) = {
  let draw(ctx, position, style) = {
    zap.interface((-style.distance / 3, -style.width / 2), (style.distance / 3, style.width / 2), io: position.len() < 2)

    let plates() = {
      cetz.draw.line((-style.distance / 3, style.width / 4), (-style.distance / 3, -style.width / 4))
      cetz.draw.line((style.distance / 3, -style.width / 2), (style.distance / 3, style.width / 2))
    }

    cetz.draw.set-style(stroke: style.stroke)
    plates()
  }

  // Component call
  zap.component("capacitor", name, node, draw: draw, ..params)
}

#let toggle-switch(name, node, ..params) = {
    assert(params.pos().len() == 0, message: "ground supports only one node")

    // Drawing function
    let draw(ctx, position, style) = {
        zap.interface((-style.width / 2, -0.2), (style.width / 2, 0.2), io: position.len() < 2)

        cetz.draw.anchor("in", (-style.width / 2, 0))
        cetz.draw.anchor("out1", (style.angle, style.width / 2))
        cetz.draw.anchor("out2", (-style.angle, style.width / 2))

 
        cetz.draw.line("in", "out1", stroke: style.stroke)
    }

    // Component call
    zap.component("toggle-switch", name, node, draw: draw, ..params, label: none)
}

#let init-zap = cetz.draw.set-ctx(ctx => {
  ctx.zap.style.insert("lamp",
    (
        scale: auto,
        stroke: auto,
        radius: .47cm,
    )
  )
  ctx.zap.style.insert("battery",
    (
        scale: auto,
        stroke: auto,
        radius: .47cm,
    )
  )
  ctx.zap.style.insert("toggle-switch",
    (
        scale: auto,
        stroke: auto,
        width: .8,
        angle: 35deg,
    )
  )
  ctx
})

#let zap-style = (
  scale: (x: 1, y: 1), 
  stroke: 0.5pt, 
  decoration: (
    symbol: none, 
    current: (
      symbol: "barbed", 
      stroke: red
    ), 
    voltage: (
      stroke: blue, 
      start: (-.3, .0), 
      end: (.3, .0), 
      center: (0, .2)
    )
  ),
  resistor: (
    label: (
      distance: 2pt
    )
  )
)

#let circuit(init: zap-style, doc) = zap.circuit({
    import zap: *
    init-zap
    zap.set-style(..init)

    doc
  })

#let circ(n) = {
  if n >= 1 and n <= 9 {
    // Der Unicode für '①' ist 9311 + n
    str.from-unicode(9311 + n)
  } else {
    n
  }
}

// Strahlen

#let ray(p1, p2, ..style) = {
  cetz.draw.line(p1, p2, ..style, name: "ray")
  cetz.draw.mark("ray.50%", "ray.end", symbol: "barbed", ..style) 
}
