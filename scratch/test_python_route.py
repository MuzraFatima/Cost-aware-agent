import asyncio
import os
from backend.app.core.router_engine import router_engine
from backend.app.core.confidence import ConfidenceEvaluator

async def main():
    p1 = await router_engine.route("What is Python?")
    print("ROUTE RESULT:")
    print("task_type:", p1.get("task_type"))
    print("complexity_score:", p1.get("complexity_score"))
    print("start_tier:", p1.get("start_tier"))
    print("final_tier:", p1.get("final_tier"))
    print("routing_reason:", p1.get("routing_reason"))
    print("steps_trace:", p1.get("steps_trace"))
    if "final_response" in p1:
        print("response excerpt:", p1["final_response"][:200])

if __name__ == "__main__":
    asyncio.run(main())
