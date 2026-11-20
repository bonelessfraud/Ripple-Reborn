"""Build step: put the #feedback webhook (repository secret FEEDBACK_WEBHOOK) into the app."""
import os

url = os.environ.get("FEEDBACK_WEBHOOK", "").strip()
path = "ripple_reborn.py"
src = open(path, encoding="utf-8").read()
src = src.replace('FEEDBACK_WEBHOOK = ""', "FEEDBACK_WEBHOOK = " + repr(url), 1)
open(path, "w", encoding="utf-8").write(src)
print("feedback webhook:", "set" if url else "not set (feature off)")
