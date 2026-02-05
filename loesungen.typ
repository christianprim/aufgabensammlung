#import "layout.typ": *
#import "auswahl.typ": daten, lösungen

#let daten = daten

#show: musterlösung.with(..daten)

#let lösungen = lösungen

#for lösung in lösungen{
  [#lösung]
}
