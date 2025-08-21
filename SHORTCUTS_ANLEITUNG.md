# iOS Shortcuts Integration für Lernkarten Generator

## 🚀 Ja, das Script kann über iOS Shortcuts gestartet werden!

### So funktioniert's:

## 1. Einfache Verwendung (nur Kartentext):
```
python3 Main.py "Vorderseite:
<h4><b>Thema: Python Basics</b></h4>
<ol>
<li>Was ist eine Variable?</li>
<li>Wie definiert man eine Funktion?</li>
<li>Was sind Listen?</li>
</ol>

Rückseite:
<h4><b>Erklärung: Python Basics</b></h4>
<p>Python ist eine <b>interpretierte Sprache</b>. Variablen speichern Werte, Funktionen mit <b>def</b> definiert.</p>
---"
```

## 2. Mit optionalen Notizen:
```
python3 Main.py "KARTENTEXT" "Meine Notizen oder Shortcuts"
```

## 📱 iOS Shortcuts App Einrichtung:

### Shortcut erstellen:
1. Öffne die **Shortcuts App**
2. Tippe auf **+** für neuen Shortcut
3. Füge folgende Aktionen hinzu:

### Aktionen:
1. **"Text"** - Hier den Kartentext eingeben oder aus Zwischenablage
2. **"Pythonista3 Script ausführen"**:
   - Script: `Main.py`
   - Argumente: Text aus Schritt 1

### Beispiel Shortcut-Konfiguration:
```
1. Text-Aktion:
   - Inhalt: "Vorderseite:..." (oder "Zwischenablage")

2. Pythonista3 ausführen:
   - Script: Main.py
   - Argumente: [Text aus vorheriger Aktion]
```

## 🎯 Verwendungsmöglichkeiten:

### A) Direkter Text im Shortcut:
- Vordefinierte Karten-Templates
- Häufig verwendete Lernkarten

### B) Aus Zwischenablage:
1. Text kopieren (z.B. aus Notes, Safari, etc.)
2. Shortcut ausführen
3. Karten werden automatisch generiert

### C) Share Sheet Integration:
- Text in beliebiger App markieren
- Teilen → Dein Shortcut
- Karten werden erstellt

## 📝 Text-Format Beispiel:
```
Vorderseite:
<h4><b>Thema: Mathematik</b></h4>
<ol>
<li>Was ist die Quadratwurzel?</li>
<li>Wie berechnet man sie?</li>
<li>Wofür wird sie verwendet?</li>
</ol>

Rückseite:
<h4><b>Erklärung: Mathematik</b></h4>
<p>Die <b>Quadratwurzel</b> einer Zahl x ist die positive Zahl, die mit sich selbst multipliziert x ergibt.</p>
---

Vorderseite:
<h4><b>Thema: Geschichte</b></h4>
<ol>
<li>Wann war der Zweite Weltkrieg?</li>
<li>Welche Länder waren beteiligt?</li>
<li>Wie endete er?</li>
</ol>

Rückseite:
<h4><b>Erklärung: Geschichte</b></h4>
<p>Der <b>Zweite Weltkrieg</b> dauerte von 1939-1945. Die <b>Alliierten</b> besiegten die Achsenmächte.</p>
---
```

## ⚡ Vorteile:
- **Schnell**: Karten direkt aus jeder App erstellen
- **Flexibel**: Text aus verschiedenen Quellen
- **Automatisch**: Keine manuelle GUI-Bedienung nötig
- **Batch**: Mehrere Karten auf einmal

## 🔧 Troubleshooting:
- Stelle sicher, dass Pythonista3 installiert ist
- Das Script muss in Pythonista verfügbar sein
- Bei Problemen: Prüfe die Textformatierung (Vorderseite:/Rückseite:)