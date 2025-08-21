# lerncharts_save_fixed.py
# Kopiere in Pythonista; lege optional eine TTF in denselben Ordner und setze FONT_PATH.

import os, re, unicodedata, io, textwrap
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import ui, photos
    UI_AVAILABLE = True
except Exception:
    UI_AVAILABLE = False

# ====== Einstellungen ======
INPUT_FILE = 'cards_raw.txt'
OUTPUT_FOLDER = '.'         # fallback speicherort
# Wenn du eine TTF in Pythonista gelegt hast, trage hier den Dateinamen ein, z.B. 'DejaVuSans.ttf'
FONT_PATH = 'arial.ttf'  # lege hier optional 'DejaVuSans.ttf' hinein
# Zielauflösung A4 landscape @200 DPI
DPI = 200
MM_TO_INCH = 0.0393701
A4_W_PX = int(297 * MM_TO_INCH * DPI)
A4_H_PX = int(210 * MM_TO_INCH * DPI)
IMG_SIZE = (A4_W_PX, A4_H_PX)
MARGIN = int(16 * MM_TO_INCH * DPI)

# Basisverzeichnis (funktioniert in Pythonista, Skript und REPL)
BASE_DIR = os.path.dirname(__file__) if '__file__' in globals() else os.getcwd()

# Erweiterte Einstellungen
# - Einzelkarten (eine pro Seite) erzeugen und optional in Foto-Galerie speichern
GENERATE_SINGLE = True
SAVE_SINGLES_TO_PHOTOS = True   # wirkt nur, wenn Pythonista/"photos" verfügbar ist

# - Druckbögen erzeugen (mehrere Karten pro Seite)
GENERATE_SHEETS = True
SHEET_GRID_COLS = 2
SHEET_GRID_ROWS = 2
SHEET_CELL_MARGIN = 0   # Kein Innenabstand - Karten grenzen direkt aneinander
SHEET_PAGE_SIZE = IMG_SIZE  # für Konsistenz: gleiche Seitengröße wie Einzelkarten

# Unterordner für getrennte Speicherung
SINGLE_SUBDIR = 'single'
SHEETS_SUBDIR = 'sheets'

# Designfarben (sanftes, modernes Layout)
BACKGROUND_COLOR = (248, 249, 252)   # leichtes Off-White
ACCENT_COLOR = (35, 99, 221)          # Blau für Kopfzeile
TITLE_TEXT_COLOR = (255, 255, 255)    # Weiß in der Kopfzeile
BODY_TEXT_COLOR = (28, 28, 30)        # fast schwarz
MUTED_TEXT_COLOR = (120, 120, 120)    # Footer/Hinweise

# Abstand zwischen Kopfzeile (Titelbalken) und Fließtext
TITLE_BODY_GAP = 60

# ====== Utilities ======
def sanitize_text(s):
    if not s: return s
    s = unicodedata.normalize('NFC', s)
    repl = {'\u2014':' - ', '\u2013':' - ', '\u2018':"'", '\u2019':"'", '\u201c':'"', '\u201d':'"',
            '\u00ab':'"', '\u00bb':'"', '\u2026':'...', '\xa0':' '}
    for k,v in repl.items(): s = s.replace(k,v)
    s = ''.join(ch for ch in s if (ch=='\n' or ch=='\t' or ord(ch) >= 32))
    return s

def strip_tags(s):
    return re.sub(r'<[^>]+>','', s).strip()

def read_raw(path):
    with open(path, 'r', encoding='utf-8') as f: return f.read()

def split_blocks(text):
    parts = re.split(r'(?m)^\s*-{3,}\s*$', text)
    return [p.strip() for p in parts if p.strip()]

# robuster Front/Back-Extractor
def extract_front_back(block):
    b = unicodedata.normalize('NFC', block)
    # Normalisiere Zeilenumbrüche, damit Regex mit ^|\n robust greift
    b = b.replace('\r\n', '\n').replace('\r', '\n')
    # 1) direkt 'Rückseite' Varianten (mit oder ohne Umlaut, mit/ohne Colon)
    m = re.search(r'(?mi)(?:^|\n)\s*(r(?:ü|u|ue)ckseite)\s*:?\s*', b)
    if m:
        front = b[:m.start()].strip()
        back  = b[m.end():].strip()
        front = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', front).strip()
        return front, back
    # 2) '===' separator fallback
    if '\n===\n' in b:
        a,c = b.split('\n===\n',1)
        a = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', a).strip()
        return a.strip(), c.strip()
    # 3) Fallback: Split am "Erklärung"-Heading, falls vorhanden
    m2 = re.search(r'(?is)<h4[^>]*>.*?erkl(?:ä|a)rung.*?</h4>', b)
    if m2:
        front = b[:m2.start()].strip()
        back  = b[m2.start():].strip()
        front = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', front).strip()
        return front, back
    # 4) Fallback: Wenn es mindestens zwei <h4>-Blöcke gibt, trenne am zweiten
    h4_iter = list(re.finditer(r'(?is)<h4[^>]*>.*?</h4>', b))
    if len(h4_iter) >= 2:
        split_at = h4_iter[1].start()
        front = b[:split_at].strip()
        back  = b[split_at:].strip()
        front = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', front).strip()
        return front, back
    # final fallback: treat whole block as front
    front = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', b).strip()
    return front, ''

def parse_card_html_like(text):
    if not text: return {'title':'', 'bullets':[], 'paragraphs':[]}
    t = text.replace('\r\n','\n').replace('\r','\n')
    # ersetze <br> zu Zeilenumbrüchen vor dem Tag-Strip
    t = re.sub(r'(?is)<br\s*/?>', '\n', t)
    t = sanitize_text(t)
    title = ''
    bullets = []
    paras = []
    m = re.search(r'(?is)<h4[^>]*>(.*?)</h4>', t)
    if m:
        title = strip_tags(m.group(1))
    # Sammle OL/UL Listenpunkte
    lists_content = re.findall(r'(?is)<ol[^>]*>(.*?)</ol>|<ul[^>]*>(.*?)</ul>', t)
    for ol_content, ul_content in lists_content:
        content = ol_content if ol_content is not None and ol_content != '' else ul_content
        if content:
            items = re.findall(r'(?is)<li[^>]*>(.*?)</li>', content)
            for it in items:
                bullets.append(strip_tags(it))
    # Paragraphen sammeln (jeder <p> kann \n enthalten, diese als einzelne Zeilen behandeln)
    paras_raw = re.findall(r'(?is)<p[^>]*>(.*?)</p>', t)
    tmp = []
    for p in paras_raw:
        stripped = strip_tags(p)
        tmp.extend([ln.strip() for ln in stripped.split('\n') if ln.strip()])
    paras = tmp
    if not title and not bullets and not paras:
        plain = strip_tags(t)
        parts = [p.strip() for p in re.split(r'\n\s*\n', plain) if p.strip()]
        if parts:
            first = parts[0]
            if len(first) < 140 and '\n' not in first and len(parts) > 1:
                title = first; paras = parts[1:]
            else:
                paras = parts
        else:
            paras = [plain]
    # Markdown/Plaintext Bullets als Fallback erkennen, falls noch keine bullets
    if not bullets:
        lines = [ln for para in paras for ln in para.split('\n') if ln.strip()]
        md_bullets = []
        for ln in lines:
            mdb = re.match(r'^\s*([-*•]|\d+[\.)])\s+(.*)$', ln)
            if mdb:
                md_bullets.append(mdb.group(2).strip())
        if len(md_bullets) >= 2:
            bullets = md_bullets
            paras = []
    title = sanitize_text(strip_tags(title))
    bullets = [sanitize_text(b) for b in bullets]
    paras = [sanitize_text(p) for p in paras]
    # Fallback: Wenn ein Titel vorhanden ist, aber weder Absätze noch Bullets erkannt wurden,
    # versuche den restlichen Inhalt ohne <h4>-Block erneut zu parsen bzw. als Plaintext zu übernehmen.
    if title and not bullets and not paras:
        body_only = re.sub(r'(?is)<h4[^>]*>.*?</h4>', '', t).strip()
        paras_raw = re.findall(r'(?is)<p[^>]*>(.*?)</p>', body_only)
        tmp = []
        for p in paras_raw:
            stripped = strip_tags(p)
            parts = [ln.strip() for ln in stripped.split('\n') if ln.strip()]
            tmp.extend(parts)
        if tmp:
            paras = [sanitize_text(p) for p in tmp]
        else:
            plain = strip_tags(body_only).strip()
            if plain:
                paras = [sanitize_text(p) for p in re.split(r'\n\s*\n', plain) if p.strip()] or [sanitize_text(plain)]
    return {'title':title, 'bullets':bullets, 'paragraphs':paras}

# ====== Font loader with clear fallback ======
def load_truetype_or_none(size):
    if not PIL_AVAILABLE: return None
    # if user provided FONT_PATH
    if FONT_PATH:
        p = os.path.join(os.path.dirname(__file__) if '__file__' in globals() else '.', FONT_PATH)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception as e:
                print('TTF konnte nicht geladen werden von', p, 'Fehler:', e)
    # try common system paths (macOS, Windows, Linux)
    candidates = [
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/HelveticaNeue.ttc',
        '/Library/Fonts/Arial.ttf',
        'C:\\Windows\\Fonts\\arial.ttf',
        'C:\\Windows\\Fonts\\Arial.ttf',
        'C:\\Windows\\Fonts\\SegoeUI.ttf',
        'C:\\Windows\\Fonts\\Tahoma.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Book.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf',
    ]
    for c in candidates:
        try:
            if os.path.exists(c):
                return ImageFont.truetype(c, size)
        except Exception:
            pass
    # not available -> return None
    return None

def measure_text(draw, text, font):
    try:
        bbox = draw.textbbox((0,0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        try:
            return draw.textsize(text, font=font)
        except Exception:
            return (len(text) * (getattr(font, 'size', 10)), getattr(font, 'size', 10))

def wrap_by_width(draw, text, font, max_w):
    words = text.split()
    if not words: return ['']
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + ' ' + w
        w_px, _ = measure_text(draw, test, font)
        if w_px <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines

# ====== Renderer (uses truetype if available; if not, prints instructions) ======
def render_front(struct, idx, fonts):
    img = Image.new('RGB', IMG_SIZE, BACKGROUND_COLOR); draw = ImageDraw.Draw(img)
    title_font, body_font, small_font = fonts
    x, y = MARGIN, MARGIN
    content_w = IMG_SIZE[0] - 2*MARGIN
    # Kopfzeile
    header_h = max(120, int(IMG_SIZE[1] * 0.22))
    draw.rectangle([0,0, IMG_SIZE[0], header_h], fill=ACCENT_COLOR)
    if struct['title']:
        lines = wrap_by_width(draw, struct['title'], title_font, content_w)
        ty = int(header_h/2)
        total_h = 0
        tmp_sizes = []
        for ln in lines:
            w, h = measure_text(draw, ln, title_font)
            tmp_sizes.append((ln,w,h))
            total_h += int(h*1.1)
        cur_y = ty - total_h//2
        for ln, w, h in tmp_sizes:
            draw.text(((IMG_SIZE[0]-w)//2, cur_y), ln, font=title_font, fill=TITLE_TEXT_COLOR)
            cur_y += int(h*1.1)
    y = header_h + TITLE_BODY_GAP
    if struct['bullets']:
        for i,b in enumerate(struct['bullets'], start=1):
            prefix = f"{i}. "
            wrapped = wrap_by_width(draw, b, body_font, content_w-80)
            for j, ln in enumerate(wrapped):
                txt = prefix + ln if j==0 else ' ' * len(prefix) + ln
                draw.text((x,y), txt, font=body_font, fill=BODY_TEXT_COLOR)
                _, h = measure_text(draw, txt, body_font)
                y += int(h * 1.2)
            y += 22
    else:
        for p in struct['paragraphs']:
            wrapped = wrap_by_width(draw, p, body_font, content_w)
            for ln in wrapped:
                draw.text((x,y), ln, font=body_font, fill=BODY_TEXT_COLOR)
                _, h = measure_text(draw, ln, body_font)
                y += int(h * 1.2)
            y += 22
    footer = f'Karte {idx} - Front'
    fw, fh = measure_text(draw, footer, small_font)
    draw.text((IMG_SIZE[0]-MARGIN-fw, IMG_SIZE[1]-MARGIN-fh), footer, font=small_font, fill=MUTED_TEXT_COLOR)
    return img

def render_back(struct, idx, fonts):
    img = Image.new('RGB', IMG_SIZE, BACKGROUND_COLOR); draw = ImageDraw.Draw(img)
    title_font, body_font, small_font = fonts
    x,y = MARGIN, MARGIN
    content_w = IMG_SIZE[0] - 2*MARGIN
    # Kopfzeile
    header_h = max(120, int(IMG_SIZE[1] * 0.22))
    draw.rectangle([0,0, IMG_SIZE[0], header_h], fill=ACCENT_COLOR)
    if struct['title']:
        lines = wrap_by_width(draw, struct['title'], title_font, content_w)
        ty = int(header_h/2)
        total_h = 0
        tmp_sizes = []
        for ln in lines:
            w, h = measure_text(draw, ln, title_font)
            tmp_sizes.append((ln,w,h))
            total_h += int(h*1.1)
        cur_y = ty - total_h//2
        for ln, w, h in tmp_sizes:
            draw.text(((IMG_SIZE[0]-w)//2, cur_y), ln, font=title_font, fill=TITLE_TEXT_COLOR)
            cur_y += int(h*1.1)
    y = header_h + TITLE_BODY_GAP
    if struct['paragraphs']:
        for p in struct['paragraphs']:
            wrapped = wrap_by_width(draw, p, body_font, content_w)
            for ln in wrapped:
                draw.text((x,y), ln, font=body_font, fill=BODY_TEXT_COLOR)
                _, h = measure_text(draw, ln, body_font)
                y += int(h * 1.2)
            y += 22
    elif struct['bullets']:
        for i,b in enumerate(struct['bullets'], start=1):
            wrapped = wrap_by_width(draw, b, body_font, content_w-80)
            for j, ln in enumerate(wrapped):
                txt = (f'{i}. ' + ln) if j==0 else (' ' * 4 + ln)
                draw.text((x,y), txt, font=body_font, fill=BODY_TEXT_COLOR)
                _, h = measure_text(draw, txt, body_font)
                y += int(h * 1.2)
            y += 22
    else:
        # Auf der Rückseite immer ein Hinweis anzeigen – hier etwas prominenter
        draw.text((x, y+40), "(keine Erklärung gefunden)", font=body_font, fill=MUTED_TEXT_COLOR)
    footer = f'Karte {idx} - Back'
    fw, fh = measure_text(draw, footer, small_font)
    draw.text((IMG_SIZE[0]-MARGIN-fw, IMG_SIZE[1]-MARGIN-fh), footer, font=small_font, fill=MUTED_TEXT_COLOR)
    return img

def compose_sheet(images, page_size, grid_cols, grid_rows, cell_margin, footer_text=None, fonts=None):
    # images: list of PIL Images (already rendered single-card images)
    page = Image.new('RGB', page_size, 'white')
    draw = ImageDraw.Draw(page)
    cell_w = page_size[0] // grid_cols
    cell_h = page_size[1] // grid_rows
    
    # Zeichne Schnittlinien für einfaches Ausschneiden
    # Vertikale Linien
    for i in range(1, grid_cols):
        x = i * cell_w
        draw.line([(x, 0), (x, page_size[1])], fill=(200, 200, 200), width=1)
    
    # Horizontale Linien
    for i in range(1, grid_rows):
        y = i * cell_h
        draw.line([(0, y), (page_size[0], y)], fill=(200, 200, 200), width=1)
    
    for idx, img in enumerate(images):
        if idx >= grid_cols * grid_rows:
            break
        col = idx % grid_cols
        row = idx // grid_cols
        x0 = col * cell_w + cell_margin
        y0 = row * cell_h + cell_margin
        x1 = (col+1) * cell_w - cell_margin
        y1 = (row+1) * cell_h - cell_margin
        # Fit image into cell keeping aspect ratio
        target_w = max(1, x1 - x0)
        target_h = max(1, y1 - y0)
        src_w, src_h = img.size
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        off_x = x0 + (target_w - new_w)//2
        off_y = y0 + (target_h - new_h)//2
        page.paste(resized, (off_x, off_y))
    
    # Footer ohne margin am unteren Rand platzieren
    if footer_text and fonts:
        _, _, small_font = fonts
        w, h = measure_text(draw, footer_text, small_font)
        draw.text((page_size[0]-w-10, page_size[1]-h-10), footer_text, font=small_font, fill=(120,120,120))
    return page

# ====== UI View (nur wenn UI verfügbar) ======
class CardGeneratorView(ui.View):
    def __init__(self):
        self.name = 'Lernkarten Generator'
        self.background_color = 'white'
        
        # Hauptcontainer
        self.scroll_view = ui.ScrollView(frame=(0, 0, self.width, self.height))
        self.scroll_view.flex = 'WH'
        self.add_subview(self.scroll_view)
        
        # Title
        title_label = ui.Label(frame=(10, 10, self.width-20, 40))
        title_label.text = 'Lernkarten Generator'
        title_label.font = ('HelveticaNeue-Medium', 24)
        title_label.alignment = ui.ALIGN_CENTER
        self.scroll_view.add_subview(title_label)
        
        # Anleitung
        instruction_label = ui.Label(frame=(10, 60, self.width-20, 260))
        instruction_label.text = '''📋 FORMATIERUNG FÜR KARTENEINGABE:

✅ STRUKTUR:
• Jede Karte wird durch drei Bindestriche (---) auf einer eigenen Zeile getrennt
• Jede Karte besteht aus "Vorderseite:" und "Rückseite:" Abschnitten
• HTML-Tags werden unterstützt für Formatierung

✅ VORDERSEITE FORMAT:
Vorderseite:
<h4><b>Thema: [Ihr Thema]</b></h4>
<ol>
  <li>[Frage 1]</li>
  <li>[Frage 2]</li>
  <li>[Frage 3]</li>
</ol>

✅ RÜCKSEITE FORMAT:
Rückseite:
<h4><b>Erklärung: [Ihr Thema]</b></h4>
<p>[Erklärungstext mit <b>wichtigen Begriffen</b> in Fettschrift]</p>
---

⚠️ WICHTIG:
• "Vorderseite:" und "Rückseite:" müssen am Zeilenanfang stehen
• Keine Leerzeichen vor "Vorderseite:" oder "Rückseite:"
• HTML-Tags müssen korrekt geschlossen werden
• Verwenden Sie <b> für Fettschrift, <ol>/<ul> für Listen'''
        instruction_label.font = ('Menlo', 10)
        instruction_label.number_of_lines = 0
        instruction_label.text_color = '#444444'
        self.scroll_view.add_subview(instruction_label)
        
        # Cards Raw Text Input
        cards_label = ui.Label(frame=(10, 330, self.width-20, 30))
        cards_label.text = 'Karteneingabe (Text):'
        cards_label.font = ('HelveticaNeue-Medium', 16)
        self.scroll_view.add_subview(cards_label)
        
        self.cards_text = ui.TextView(frame=(10, 365, self.width-20, 300))
        self.cards_text.font = ('Menlo', 12)
        self.cards_text.border_width = 1
        self.cards_text.border_color = '#CCCCCC'
        self.cards_text.corner_radius = 5
        # Beispieltext einfügen
        self.cards_text.text = '''Vorderseite:
<h4><b>Thema: Beispielthema</b></h4>
<ol>
<li>Was ist die erste Frage?</li>
<li>Was ist die zweite Frage?</li>
<li>Was ist die dritte Frage?</li>
</ol>

Rückseite:
<h4><b>Erklärung: Beispielthema</b></h4>
<p>Hier kommt die Erklärung mit <b>wichtigen Begriffen</b> in Fettschrift.</p>
---'''
        self.scroll_view.add_subview(self.cards_text)
        
        # Shortcut Input
        shortcut_label = ui.Label(frame=(10, 675, self.width-20, 30))
        shortcut_label.text = 'Shortcuts (optional):'
        shortcut_label.font = ('HelveticaNeue-Medium', 16)
        self.scroll_view.add_subview(shortcut_label)
        
        self.shortcut_text = ui.TextField(frame=(10, 710, self.width-20, 40))
        self.shortcut_text.font = ('HelveticaNeue', 14)
        self.shortcut_text.placeholder = 'z.B. Tastenkombinationen oder Notizen'
        self.shortcut_text.border_width = 1
        self.shortcut_text.border_color = '#CCCCCC'
        self.shortcut_text.corner_radius = 5
        self.scroll_view.add_subview(self.shortcut_text)
        
        # Generate Button
        self.generate_btn = ui.Button(frame=(10, 760, self.width-20, 50))
        self.generate_btn.title = 'Karten generieren'
        self.generate_btn.bg_color = '#007AFF'
        self.generate_btn.tint_color = 'white'
        self.generate_btn.font = ('HelveticaNeue-Medium', 18)
        self.generate_btn.corner_radius = 10
        self.generate_btn.action = self.generate_cards
        self.scroll_view.add_subview(self.generate_btn)
        
        # Status Label
        self.status_label = ui.Label(frame=(10, 820, self.width-20, 40))
        self.status_label.text = ''
        self.status_label.font = ('HelveticaNeue', 14)
        self.status_label.text_color = '#666666'
        self.status_label.alignment = ui.ALIGN_CENTER
        self.status_label.number_of_lines = 0
        self.scroll_view.add_subview(self.status_label)
        
        # Set content size
        self.scroll_view.content_size = (self.width, 870)
    
    def generate_cards(self, sender):
        self.status_label.text = 'Generiere Karten...'
        # Den eingegebenen Text verwenden statt der Datei
        raw_text = self.cards_text.text
        shortcut_text = self.shortcut_text.text
        
        # Temporär den Text in cards_raw speichern (für Kompatibilität)
        temp_file = os.path.join(BASE_DIR, 'temp_cards_raw.txt')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        
        # Main generation logic aufrufen
        try:
            generate_from_text(raw_text, shortcut_text)
            self.status_label.text = 'Karten erfolgreich generiert!'
        except Exception as e:
            self.status_label.text = f'Fehler: {str(e)}'
        finally:
            # Temp file aufräumen
            if os.path.exists(temp_file):
                os.remove(temp_file)

# ====== Modified Main logic ======
def generate_from_text(raw_text, shortcut_text=None):
    print('Start generation...')
    output_dir = OUTPUT_FOLDER if os.path.isabs(OUTPUT_FOLDER) else os.path.join(BASE_DIR, OUTPUT_FOLDER)
    os.makedirs(output_dir, exist_ok=True)
    
    # Separate Ausgabeverzeichnisse
    single_dir = os.path.join(output_dir, SINGLE_SUBDIR)
    sheets_dir = os.path.join(output_dir, SHEETS_SUBDIR)
    if GENERATE_SINGLE:
        os.makedirs(single_dir, exist_ok=True)
    if GENERATE_SHEETS:
        os.makedirs(sheets_dir, exist_ok=True)
    
    if not PIL_AVAILABLE:
        print('Pillow (PIL) ist nicht verfügbar. Bitte installiere Pillow, z.B. via apt: sudo apt-get install -y python3-pil')
        raise Exception('PIL nicht verfügbar')
    
    blocks = split_blocks(raw_text)
    cards = [extract_front_back(b) for b in blocks]
    print('Gefundene Karten:', len(cards))
    
    # Load fonts
    title_size = 128; body_size = 54; small_size = 22
    tt_title = load_truetype_or_none(title_size)
    tt_body  = load_truetype_or_none(body_size)
    tt_small = load_truetype_or_none(small_size)
    if tt_title is None or tt_body is None:
        print('Warnung: Keine TrueType-Schrift gefunden.')
        tt_title = ImageFont.load_default()
        tt_body  = ImageFont.load_default()
        tt_small = ImageFont.load_default()
    fonts = (tt_title, tt_body, tt_small)
    
    saved = 0
    sheet_images_front = []
    sheet_images_back = []
    
    for i, (front_raw, back_raw) in enumerate(cards, start=1):
        front = parse_card_html_like(front_raw)
        back  = parse_card_html_like(back_raw)
        print(f'Karte {i}: Processing...')
        
        try:
            img_f = render_front(front, i, fonts)
        except Exception as e:
            print('Fehler Front render:', e)
            continue
            
        try:
            if GENERATE_SINGLE:
                if UI_AVAILABLE and SAVE_SINGLES_TO_PHOTOS:
                    buf = io.BytesIO()
                    img_f.save(buf,'PNG')
                    photos.save_image(ui.Image.from_data(buf.getvalue()))
                    print('Saved to Photos (front)', i)
                p_single = os.path.join(single_dir, f'card_{i:02d}_front.png')
                img_f.save(p_single)
                print('Saved', p_single)
                saved += 1
            if GENERATE_SHEETS:
                sheet_images_front.append(img_f)
        except Exception as e:
            print('Fehler speichern front:', e)
        
        try:
            img_b = render_back(back, i, fonts)
        except Exception as e:
            print('Fehler Back render:', e)
            continue
            
        try:
            if GENERATE_SINGLE:
                if UI_AVAILABLE and SAVE_SINGLES_TO_PHOTOS:
                    buf = io.BytesIO()
                    img_b.save(buf,'PNG')
                    photos.save_image(ui.Image.from_data(buf.getvalue()))
                    print('Saved to Photos (back)', i)
                p_single = os.path.join(single_dir, f'card_{i:02d}_back.png')
                img_b.save(p_single)
                print('Saved', p_single)
                saved += 1
            if GENERATE_SHEETS:
                sheet_images_back.append(img_b)
        except Exception as e:
            print('Fehler speichern back:', e)
    
    # Druckbögen generieren
    if GENERATE_SHEETS:
        cards_per_sheet = SHEET_GRID_COLS * SHEET_GRID_ROWS
        def chunks(lst, n):
            for k in range(0, len(lst), n):
                yield lst[k:k+n]
        
        page_idx = 1
        for batch in chunks(sheet_images_front, cards_per_sheet):
            page = compose_sheet(batch, SHEET_PAGE_SIZE, SHEET_GRID_COLS, SHEET_GRID_ROWS, 
                               SHEET_CELL_MARGIN, footer_text=f'Sheet Front {page_idx}', fonts=fonts)
            out_path = os.path.join(sheets_dir, f'sheet_{page_idx:02d}_front.png')
            try:
                page.save(out_path)
                print('Saved', out_path)
            except Exception as e:
                print('Fehler speichern sheet front:', e)
            page_idx += 1
            
        page_idx = 1
        for batch in chunks(sheet_images_back, cards_per_sheet):
            page = compose_sheet(batch, SHEET_PAGE_SIZE, SHEET_GRID_COLS, SHEET_GRID_ROWS, 
                               SHEET_CELL_MARGIN, footer_text=f'Sheet Back {page_idx}', fonts=fonts)
            out_path = os.path.join(sheets_dir, f'sheet_{page_idx:02d}_back.png')
            try:
                page.save(out_path)
                print('Saved', out_path)
            except Exception as e:
                print('Fehler speichern sheet back:', e)
            page_idx += 1
    
    print('Fertig. Bilder erzeugt/gespeichert:', saved)
    return saved

# ====== Main ======
def main():
    print('Start...')
    
    # Wenn UI verfügbar ist, GUI zeigen
    if UI_AVAILABLE:
        v = CardGeneratorView()
        v.present('sheet')
    else:
        # Fallback auf Datei-basierte Verarbeitung
        input_path = INPUT_FILE if os.path.isabs(INPUT_FILE) else os.path.join(BASE_DIR, INPUT_FILE)
        if not os.path.exists(input_path):
            print('cards_raw.txt nicht gefunden im Ordner. Bitte anlegen. Pfad versucht:', input_path)
            return
        
        raw = read_raw(input_path)
        generate_from_text(raw)

if __name__ == '__main__':
    main()