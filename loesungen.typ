#import "layout.typ": *
#import "auswahl.typ": daten, lösungen

#show: musterlösung.with(..daten)

#for lösung in lösungen{
  [#lösung]
}
