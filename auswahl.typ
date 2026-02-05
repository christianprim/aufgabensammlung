#let art = "Prüfung"
// #let art = "Nachprüfung"
#let klasse = "Klassenbezeichnung"
#let datum = "1.1.2000"

#let daten = (art: art, klasse: klasse, datum: datum)

#let aufgaben = ()
#let lösungen = ()

// GEBIET
// ======
//
// Einfache Aufgabe mit Zeichnung
// Eingesetzt: Klasse (Semester), 
#import "vorlage/einfach.typ": aufgabe, lösung; #aufgaben.push([#aufgabe]); #lösungen.push([#lösung])
//
// Aufgabe mit Unteraufgaben und Bild
// Eingesetzt: 
#import "vorlage/unteraufgaben.typ": aufgabe, lösung; #aufgaben.push([#aufgabe]); #lösungen.push([#lösung])
