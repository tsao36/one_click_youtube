import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

import re
from agents.scene_planner import REAL_MEDIA_PATTERNS, PERSON_ENTITY_REGEX

# Test pattern matching on 沈柏洋 and 黑熊學院
test_samples = [
    ("在沈柏洋的辦公室裡，動漫公仔與戰鬥陀螺並排而立", "Puma Shen standing in modern office", "沈柏洋人生經歷一路到現在選戰超前"),
    ("黑熊學院不僅提供實質的訓練課程，還積極推廣防災與應急的知識", "Kuma academy civil defense training hall", "沈柏洋人生經歷一路到現在選戰超前"),
    ("在2024年，沈柏洋成功進入立法院，並被分配到外交及國防委員會", "Legislative Yuan debate chamber podium", "沈柏洋人生經歷一路到現在選戰超前"),
    ("黃國昌在立法院質詢官員，神情嚴肅", "Huang Kuo-chang speaking at legislative podium", "黃國昌人生哲學：從學霸到立院戰神"),
    ("展示一塊高精密矽晶圓晶片特寫", "macro shot of silicon wafer circuit board", "台灣半導體傳奇"),
]

print("Testing samples...")
# We will verify how they resolve with our new patterns and logic
