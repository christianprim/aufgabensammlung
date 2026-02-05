#import "../layout.typ": *

#let aufgabe = {
  [
    = Titel meiner Aufgabe
    #p(3) #grid(
      columns: (1fr, auto),
      gutter: .5cm,
      [
        Hier folgt der Aufgabentext. 

        #lorem(50)
      ],
      [
        #cetz.canvas({
          import cetz.draw: *
          set-style(stroke: .5pt)

          circle((), radius: 1.5, stroke: aqua)
        })
      ]
    )
    #schreibpapier()
    #pagebreak()
  ]
}

#let lösung = {
  [
    = Titel meiner Aufgabe
    $F = m a$; #qty("10", "Newton")
  ]
}
