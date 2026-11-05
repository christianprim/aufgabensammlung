#import "layout.typ": *
#import "auswahl.typ": daten, aufgaben

#let desired-page-number = 8

#show: prüfung.with(..daten)

#for aufgabe in aufgaben{
  [#aufgabe]
}

#context {
  let pages-so-far = here().page()
  for pages in range(desired-page-number - pages-so-far){
    schreibpapier()
    pagebreak()
  }
}
#set page(footer: [])
