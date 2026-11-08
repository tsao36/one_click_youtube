from pathlib import Path

pipe_path = Path("core/documentary_pipeline.py")
content = pipe_path.read_text(encoding="utf-8")

old_block = '''            self.p.path("script", "script.md").write_text(script_markdown(scr), encoding="utf-8")



            self.p.data.title = scr.get("title", self.p.data.topic)'''

new_block = '''            self.p.path("script", "script.md").write_text(script_markdown(scr), encoding="utf-8")

            # Stage 2: Fact check script against research dossier to catch hallucinations and invalid multipliers
            try:
                self.p.activity("Stage 2/10: Verifying script factual grounding & numbers...")
                from core.fact_checker import verify_script_facts
                verify_script_facts(self.p, on_request=self._track_llm_request, provider_override=scr_prov, auto_patch=True)
            except Exception as fce:
                log.warning("Stage 2 script fact verification failed: %s", fce)

            self.p.data.title = scr.get("title", self.p.data.topic)'''

assert old_block in content, "old_block not found in core/documentary_pipeline.py"
content = content.replace(old_block, new_block)
pipe_path.write_text(content, encoding="utf-8")
print("Successfully inserted script fact check step into Stage 2 of core/documentary_pipeline.py!")
