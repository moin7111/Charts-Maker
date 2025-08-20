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
    # 3) try to find last <h4> or last <p> and assume everything after it is back (best-effort)
    # (This is a second-level fallback; often unnecessary)
    # final fallback: treat whole block as front
    front = re.sub(r'(?is)^\s*vorderseite\s*:\s*','', b).strip()
    return front, ''

def parse_card_html_like(text):
    if not text: return {'title':'', 'bullets':[], 'paragraphs':[]}
    t = text.replace('\r\n','\n').replace('\r','\n')
    t = sanitize_text(t)
    title = ''
    bullets = []
    paras = []
    m = re.search(r'(?is)<h4[^>]*>(.*?)</h4>', t)
    if m: title = strip_tags(m.group(1))
    m2 = re.search(r'(?is)<ol[^>]*>(.*?)</ol>', t)
    if m2:
        items = re.findall(r'(?is)<li[^>]*>(.*?)</li>', m2.group(1))
        bullets = [strip_tags(it) for it in items]
    paras_raw = re.findall(r'(?is)<p[^>]*>(.*?)</p>', t)
    paras = [strip_tags(p) for p in paras_raw]
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
    title = sanitize_text(strip_tags(title))
    bullets = [sanitize_text(b) for b in bullets]
    paras = [sanitize_text(p) for p in paras]
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
    # try common system paths
    candidates = ['/System/Library/Fonts/Helvetica.ttc','/System/Library/Fonts/HelveticaNeue.ttc','/Library/Fonts/Arial.ttf']
    for c in candidates:
        try:
            if os.path.exists(c):
                return ImageFont.truetype(c, size)
        except Exception:
            pass
    # not available -> return None
    return None

def wrap_by_width(draw, text, font, max_w):
    words = text.split()
    if not words: return ['']
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + ' ' + w
        try:
            w_px = draw.textbbox((0,0), test, font=font)[2]
        except Exception:
            w_px = draw.textsize(test, font=font)[0]
        if w_px <= max_w: cur = test
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines

# ====== Renderer (uses truetype if available; if not, prints instructions) ======
def render_front(struct, idx, fonts):
    img = Image.new('RGB', IMG_SIZE, 'white'); draw = ImageDraw.Draw(img)
    title_font, body_font, small_font = fonts
    x, y = MARGIN, MARGIN
    content_w = IMG_SIZE[0] - 2*MARGIN
    if struct['title']:
        lines = wrap_by_width(draw, struct['title'], title_font, content_w)
        for ln in lines:
            w = draw.textbbox((0,0), ln, font=title_font)[2]
            draw.text(((IMG_SIZE[0]-w)//2, y), ln, font=title_font, fill=(10,10,10))
            y += int(draw.textbbox((0,0), ln, font=title_font)[3] * 1.1)
        y += 20
    if struct['bullets']:
        for i,b in enumerate(struct['bullets'], start=1):
            prefix = f"{i}. "
            wrapped = wrap_by_width(draw, b, body_font, content_w-80)
            for j, ln in enumerate(wrapped):
                txt = prefix + ln if j==0 else ' ' * len(prefix) + ln
                draw.text((x,y), txt, font=body_font, fill=(30,30,30))
                y += int(draw.textbbox((0,0), txt, font=body_font)[3] * 1.2)
            y += 12
    else:
        for p in struct['paragraphs']:
            wrapped = wrap_by_width(draw, p, body_font, content_w)
            for ln in wrapped:
                draw.text((x,y), ln, font=body_font, fill=(30,30,30))
                y += int(draw.textbbox((0,0), ln, font=body_font)[3] * 1.2)
            y += 18
    footer = f'Karte {idx} - Front'
    fw = draw.textbbox((0,0), footer, font=small_font)[2]
    fh = draw.textbbox((0,0), footer, font=small_font)[3]
    draw.text((IMG_SIZE[0]-MARGIN-fw, IMG_SIZE[1]-MARGIN-fh), footer, font=small_font, fill=(120,120,120))
    return img

def render_back(struct, idx, fonts):
    img = Image.new('RGB', IMG_SIZE, 'white'); draw = ImageDraw.Draw(img)
    title_font, body_font, small_font = fonts
    x,y = MARGIN, MARGIN
    content_w = IMG_SIZE[0] - 2*MARGIN
    if struct['title']:
        lines = wrap_by_width(draw, struct['title'], title_font, content_w)
        for ln in lines:
            w = draw.textbbox((0,0), ln, font=title_font)[2]
            draw.text(((IMG_SIZE[0]-w)//2, y), ln, font=title_font, fill=(10,10,10))
            y += int(draw.textbbox((0,0), ln, font=title_font)[3] * 1.1)
        y += 18
    if struct['paragraphs']:
        for p in struct['paragraphs']:
            wrapped = wrap_by_width(draw, p, body_font, content_w)
            for ln in wrapped:
                draw.text((x,y), ln, font=body_font, fill=(30,30,30))
                y += int(draw.textbbox((0,0), ln, font=body_font)[3] * 1.2)
            y += 18
    elif struct['bullets']:
        for i,b in enumerate(struct['bullets'], start=1):
            wrapped = wrap_by_width(draw, b, body_font, content_w-80)
            for j, ln in enumerate(wrapped):
                txt = (f'{i}. ' + ln) if j==0 else (' ' * 4 + ln)
                draw.text((x,y), txt, font=body_font, fill=(30,30,30))
                y += int(draw.textbbox((0,0), txt, font=body_font)[3] * 1.2)
            y += 12
    else:
        draw.text((x, y+40), "(keine Erklärung gefunden)", font=body_font, fill=(160,160,160))
    footer = f'Karte {idx} - Back'
    fw = draw.textbbox((0,0), footer, font=small_font)[2]
    fh = draw.textbbox((0,0), footer, font=small_font)[3]
    draw.text((IMG_SIZE[0]-MARGIN-fw, IMG_SIZE[1]-MARGIN-fh), footer, font=small_font, fill=(120,120,120))
    return img

# ====== Main ======
def main():
    print('Start...')
    if not os.path.exists(INPUT_FILE):
        print('cards_raw.txt nicht gefunden im Ordner. Bitte anlegen.'); return
    if not PIL_AVAILABLE:
        print('Pillow nicht verfügbar. Bitte Pillow in Pythonista installieren.'); return

    raw = read_raw(INPUT_FILE)
    blocks = split_blocks(raw)
    cards = [extract_front_back(b) for b in blocks]
    print('Gefundene Karten:', len(cards))

    # Load fonts: try TTF; if not available, abort with instruction
    title_size = 140; body_size = 56; small_size = 20
    tt_title = load_truetype_or_none(title_size)
    tt_body  = load_truetype_or_none(body_size)
    tt_small = load_truetype_or_none(small_size)
    if tt_title is None or tt_body is None:
        print('Warnung: Keine TrueType-Schrift gefunden. Für optimale Darstellung lege eine TTF (z.B. DejaVuSans.ttf) in den selben Ordner und setze FONT_PATH.')
        # still allow fallback, but use load_default (may be small)
        tt_title = ImageFont.load_default()
        tt_body  = ImageFont.load_default()
        tt_small = ImageFont.load_default()
    fonts = (tt_title, tt_body, tt_small)

    saved = 0
    for i, (front_raw, back_raw) in enumerate(cards, start=1):
        front = parse_card_html_like(front_raw)
        back  = parse_card_html_like(back_raw)
        print(f'Karte {i}: title_front_len={len(front["title"])}, bullets={len(front["bullets"])}, paras_front={len(front["paragraphs"])}, title_back_len={len(back["title"])}, paras_back={len(back["paragraphs"])}')

        try:
            img_f = render_front(front, i, fonts)
        except Exception as e:
            print('Fehler Front render:', e); continue
        try:
            if UI_AVAILABLE:
                buf = io.BytesIO(); img_f.save(buf,'PNG'); photos.save_image(ui.Image.from_data(buf.getvalue()))
            else:
                p = os.path.join(OUTPUT_FOLDER, f'card_{i:02d}_front.png'); img_f.save(p); print('Saved',p)
            saved += 1
        except Exception as e:
            print('Fehler speichern front:', e)

        try:
            img_b = render_back(back, i, fonts)
        except Exception as e:
            print('Fehler Back render:', e); continue
        try:
            if UI_AVAILABLE:
                buf = io.BytesIO(); img_b.save(buf,'PNG'); photos.save_image(ui.Image.from_data(buf.getvalue()))
            else:
                p = os.path.join(OUTPUT_FOLDER, f'card_{i:02d}_back.png'); img_b.save(p); print('Saved',p)
            saved += 1
        except Exception as e:
            print('Fehler speichern back:', e)

    print('Fertig. Bilder erzeugt/gespeichert:', saved)

if __name__ == '__main__':
    main()
