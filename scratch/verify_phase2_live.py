import asyncio
from backend.app.core.router_engine import router_engine

async def verify():
    prompts = [
        "What is Python?",
        "Write a Python program to sort a list.",
        "Design a complex multi-agent reinforcement learning system."
    ]

    print("================ PHASE 2 LIVE ROUTING VERIFICATION ================")
    for idx, prompt in enumerate(prompts, 1):
        result = await router_engine.route(prompt)
        last_step = result["usage"]["routing_path"][-1] if result["usage"].get("routing_path") else {}
        model_used = last_step.get("model_name", "groq/openai/gpt-oss-20b")
        
        print(f"\n--- Test Question {idx}: '{prompt}' ---")
        print(f"Task Type:       {result.get('task_type')}")
        print(f"Complexity Score:{result.get('complexity_score')}/10")
        print(f"Selected Tier:   Tier {result.get('final_tier')}")
        print(f"Selected Model:  {model_used}")
        print(f"Routing Reason:  {result.get('routing_reason')}")
        print(f"Cost USD:        ${result['usage']['total_cost_usd']:.6f}")
        print(f"Latency MS:      {result['usage']['total_latency_ms']} ms")
        clean_text = result['text'][:120].encode('ascii', 'ignore').decode('ascii').replace('\n', ' ')
        print(f"Response Excerpt:{clean_text}...")
    print("\n====================================================================")

if __name__ == "__main__":
    asyncio.run(verify())
