from PIL import Image, ImageDraw
import os
from xml.dom.minidom import Document

def save_svg(name, svg_content):
    with open(f"icons/{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)

os.makedirs('icons', exist_ok=True)
icons = [
    'player_play','player_pause','player_seek-backward','player_seek-forward',
    'player_volume','player_volume-mute','player_repeat','player_shuffle','player_chevron-down',
    'player_remove','player_up','player_down','player_save'
]
colors = {'bg': (30,30,30), 'fg': (255,255,255)}
for name in icons:
    # SVG 생성
    if 'pause' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <rect x="10" y="8" width="8" height="32" fill="white"/>
  <rect x="30" y="8" width="8" height="32" fill="white"/>
</svg>'''
    elif 'seek-backward' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="34,8 34,40 14,24" fill="white"/>
  <rect x="8" y="8" width="8" height="32" fill="white"/>
</svg>'''
    elif 'seek-forward' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="14,8 14,40 34,24" fill="white"/>
  <rect x="36" y="8" width="8" height="32" fill="white"/>
</svg>'''
    elif 'volume-mute' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <rect x="8" y="18" width="16" height="12" fill="white"/>
  <line x1="28" y1="16" x2="40" y2="32" stroke="red" stroke-width="4"/>
  <line x1="28" y1="32" x2="40" y2="16" stroke="red" stroke-width="4"/>
</svg>'''
    elif 'volume' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <rect x="8" y="18" width="16" height="12" fill="white"/>
  <path d="M28 24a8 8 0 0 1 8 8" stroke="white" stroke-width="4" fill="none"/>
</svg>'''
    elif 'repeat' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <path d="M10 16h24l-4-4" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M38 32H14l4 4" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
    elif 'shuffle' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <line x1="10" y1="38" x2="38" y2="10" stroke="white" stroke-width="4"/>
  <line x1="10" y1="10" x2="38" y2="38" stroke="white" stroke-width="4"/>
</svg>'''
    elif 'chevron-down' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="12,18 24,34 36,18" fill="white"/>
</svg>'''
    elif 'remove' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <line x1="12" y1="12" x2="36" y2="36" stroke="red" stroke-width="6"/>
  <line x1="36" y1="12" x2="12" y2="36" stroke="red" stroke-width="6"/>
</svg>'''
    elif 'up' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="24,10 10,34 38,34" fill="white"/>
</svg>'''
    elif 'down' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="10,14 38,14 24,38" fill="white"/>
</svg>'''
    elif 'save' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <rect x="12" y="12" width="24" height="24" stroke="white" stroke-width="4" fill="none"/>
  <rect x="18" y="24" width="12" height="10" fill="white"/>
</svg>'''
    elif 'play' in name:
        svg = '''<svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="48" height="48" fill="#1e1e1e"/>
  <polygon points="14,8 14,40 38,24" fill="white"/>
</svg>'''
    else:
        svg = ''
    if svg:
        save_svg(name, svg)
print('샘플 아이콘(PNG, SVG) 생성 완료!') 