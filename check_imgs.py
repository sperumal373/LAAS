import re, base64, os
with open(r'C:\caas-dashboard\USER_MANUAL.html', encoding='utf-8', errors='replace') as f:
    content = f.read()

imgs = re.findall(r'data:image/([a-z]+);base64,([A-Za-z0-9+/=]{100,})', content)
print('Base64 images found:', len(imgs))

# Extract each screenshot
os.makedirs(r'C:\caas-dashboard\screenshots', exist_ok=True)
for i, (fmt, data) in enumerate(imgs):
    try:
        img_bytes = base64.b64decode(data)
        path = rf'C:\caas-dashboard\screenshots\screenshot_{i+1:02d}.{fmt}'
        with open(path, 'wb') as f2:
            f2.write(img_bytes)
        print(f'  Saved: screenshot_{i+1:02d}.{fmt}  ({len(img_bytes)//1024} KB)')
    except Exception as e:
        print(f'  Error {i+1}: {e}')

# Also check <img src= tags (non-base64)
img_tags = re.findall(r'<img [^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']', content)
img_tags += re.findall(r'<img [^>]*alt=["\']([^"\']*)["\'][^>]*src=["\']([^"\']+)["\']', content)
print('Non-base64 img refs:', img_tags[:10])
