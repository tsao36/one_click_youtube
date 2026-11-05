with open('generators/remotion_cards.py', 'rb') as f:
    text = f.read().decode('utf-8')
text = text.replace('p["dim"] = float(p.get("dim") or 0.35)', 'p["dim"] = float(p.get("dim") or 0.0)', 1)
with open('generators/remotion_cards.py', 'wb') as f:
    f.write(text.encode('utf-8'))
print('Updated dim in remotion_cards.py')
