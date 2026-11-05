# encoding: utf-8
with open("core/documentary_pipeline.py", "rb") as f:
    content = f.read().decode("utf-8")

old_code = "self.p.set_scenes(scenes)"
new_code = """self.p.set_scenes(scenes)

            # Automatically enforce >= 90% real images/footage for scenes mentioning main character
            try:
                from core.character_detector import enforce_main_character_real_image_ratio
                enforce_main_character_real_image_ratio(self.p, ratio=0.9)
            except Exception as enf_err:
                log.warning("Auto enforcement of 90% real images for main character skipped: %s", enf_err)"""

assert old_code in content, "old_code not found"
content = content.replace(old_code, new_code, 1)

with open("core/documentary_pipeline.py", "wb") as f:
    f.write(content.encode("utf-8"))

print("core/documentary_pipeline.py successfully patched!")
