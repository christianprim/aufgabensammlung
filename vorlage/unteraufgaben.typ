#import "../layout.typ": *

#let aufgabe = {
  [
    = Aufgabe mit Unteraufgaben
    #grid(
       columns: (auto, 1fr),
       gutter: .5cm,
       [
         #image("../bilder/bild.jpg", width: 4cm)
       ],
       [
         Hier mein Aufgabentext mit einer Massangabe #qty("12", "m").

         #lorem(80)
       ]
     ) 
    + #p(1) Eine einfachere Einstiegsfrage.
      #schreibpapier(height: 6cm)

    + #p(1) Eine weitere Frage.
      #schreibpapier(height: 6cm)

    + #p(1) Und die letzte Frage.
      #schreibpapier()
    #pagebreak()
  ]
}

#let lösung = {
  [
    = Aufgabe mit Unteraufgaben
    + $B=G b/g$; #qty("2.1", "m")

    + $f=(1/g +1/b)^(-1)$; #qty("1.5", "cm")

    + Das wäre meine Textantwort
  ]
}
