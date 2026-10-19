"""Run once to check the key, the model name and the logging work:  python smoke_test.py"""
from testdebt.llm_client import LLMClient, total_tokens

llm = LLMClient()
r = llm.chat([{"role": "user", "content": "Reply with exactly: OK"}], tag="smoke_test", max_tokens=200)
print("model :", r["model"])
print("text  :", r["text"])
print("usage :", r["usage"])
print("cached:", r["cached"], "| latency:", r["latency_s"], "s")
print("tokens used so far (uncached):", total_tokens())
