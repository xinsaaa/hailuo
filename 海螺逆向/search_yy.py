import urllib.request, re, os, json

OUT = r'c:/Users/xinxin/Desktop/海螺逆向/js_chunks'
os.makedirs(OUT, exist_ok=True)

# Step 1: fetch index page
print('[*] Fetching index page...')
req = urllib.request.Request(
    'https://hailuoai.com/create/image-to-video',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode('utf-8', errors='ignore')
except Exception as e:
    print(f'Failed to fetch index: {e}')
    exit(1)

urls = list(set(re.findall(r'https://cdn\.hailuoai\.com/[^"]+\.js', html)))
print(f'[*] Found {len(urls)} JS URLs')

# Step 2: download each JS file
for url in sorted(urls):
    fname = os.path.basename(url)
    fpath = os.path.join(OUT, fname)
    if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        continue
    try:
        req2 = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2, timeout=20) as r:
            data = r.read()
        with open(fpath, 'wb') as f:
            f.write(data)
        print(f'  Downloaded: {fname} ({len(data)} bytes)')
    except Exception as e:
        print(f'  FAIL: {fname}: {e}')

# Step 3: search for Yy patterns
print('\n[*] Searching for Yy patterns...')
results = {}
for fname in os.listdir(OUT):
    if not fname.endswith('.js') or 'polyfill' in fname:
        continue
    fpath = os.path.join(OUT, fname)
    try:
        with open(fpath, 'r', errors='ignore') as f:
            content = f.read()
    except:
        continue

    patterns = [
        r'.{0,150}["\']Yy["\'].{0,150}',
        r'.{0,150}Yy[\s]*[:=][^=].{0,100}',
        r'.{0,100}headers.*Yy.{0,100}',
    ]
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, content):
            txt = m.group().strip()
            if txt not in matches:
                matches.append(txt)

    if matches:
        results[fname] = matches
        print(f'\n=== {fname} ===')
        for m in matches[:10]:
            print(f'  {m[:300]}')

if not results:
    print('[!] No Yy pattern found in any JS file')
    print('[*] Trying broader search for signature/sign/token header setters...')
    for fname in os.listdir(OUT):
        if not fname.endswith('.js') or 'polyfill' in fname:
            continue
        fpath = os.path.join(OUT, fname)
        with open(fpath, 'r', errors='ignore') as f:
            content = f.read()
        for pat in [r'headers\[.{0,20}\]\s*=', r'interceptors\.request', r'sign.*=.*function']:
            for m in re.finditer(pat, content):
                ctx = content[max(0, m.start()-100):m.end()+200]
                print(f'[{fname}] {ctx[:400]}')
                break
print('\n[DONE]')
