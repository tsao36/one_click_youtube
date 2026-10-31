import re, subprocess
p = r'c:\AI Project\Youtube_video\ui\index.html'
s = open(p, 'rb').read().decode('utf-8')
old = '''<button type="button" class="btn-sec" onclick="switchTab('preview')" style="font-size: 13px; padding: 12px 18px; border-color: rgba(245, 158, 11, 0.4); color: #fde68a;">\r\n            📺 前往 Player'''
assert s.count(old) == 1
new = '''<button type="button" class="btn-sec" onclick="switchTab('dramastudio')" style="font-size: 13px; padding: 12px 18px; border-color: rgba(124, 58, 237, 0.5); color: #c4b5fd;">\r\n            🎭 Drama Stage Studio\r\n          </button>\r\n          ''' + old
s = s.replace(old, new)
open(p, 'wb').write(s.encode('utf-8'))
m = re.findall(r'<script(?![^>]*src)[^>]*>(.*?)</script>', s, re.S)
open(r'c:\AI Project\Youtube_video\scratch\bak\chk.js', 'w', encoding='utf-8').write(m[0])
r = subprocess.run(['node', '--check', r'c:\AI Project\Youtube_video\scratch\bak\chk.js'], capture_output=True, text=True)
print('node exit', r.returncode, r.stderr[:300])
