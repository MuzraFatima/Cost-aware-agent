import asyncio
from backend.app.core.router_engine import router_engine
from backend.app.utils.cost_tracker import calculate_budget_status

async def verify():
    print("================ PHASE 3 COST & BUDGET INTELLIGENCE VERIFICATION ================")
    
    # 1. Budget Status
    status = calculate_budget_status()
    print(f"\n--- 1. Current Budget Intelligence Status ---")
    print(f"Daily Budget Limit:        ${status['daily_budget_usd']:.2f}")
    print(f"Monthly Budget Limit:      ${status['monthly_budget_usd']:.2f}")
    print(f"Daily Spent Today:         ${status['daily_spent_usd']:.6f}")
    print(f"Monthly Spent This Month:  ${status['monthly_spent_usd']:.6f}")
    print(f"Remaining Daily Budget:    ${status['remaining_daily_budget_usd']:.6f}")
    print(f"Budget Pressure Score:     {status['budget_pressure_score']} / 100")
    print(f"Avg Cost / Request:        ${status['avg_cost_per_request_usd']:.6f}")

    # 2. Query with Low Pressure
    prompt1 = "What is Python?"
    r1 = await router_engine.route(prompt1)
    print(f"\n--- 2. Low Pressure Decision: '{prompt1}' ---")
    print(f"Task Type:                 {r1.get('task_type')}")
    print(f"Complexity Score:          {r1.get('complexity_score')}/10")
    print(f"Budget Pressure Score:     {r1.get('budget_pressure_score')}/100")
    print(f"Pre-Request Cost Est.:     ${r1.get('pre_request_estimated_cost_usd'):.6f}")
    print(f"Actual Request Cost:       ${r1['usage']['total_cost_usd']:.6f}")
    print(f"Selected Tier & Model:     Tier {r1.get('final_tier')} ({r1.get('selected_model')})")
    reason1 = r1.get('routing_reason', '').encode('ascii', 'ignore').decode('ascii')
    print(f"Routing Reason:            {reason1}")

    # 3. Query with Per-Request Budget Cap Downgrade
    prompt2 = "Design a complex multi-agent reinforcement learning system."
    r2 = await router_engine.route(prompt2, budget_limit_usd=0.0002)
    print(f"\n--- 3. Budget Cap Downgrade Decision: '{prompt2}' (Cap: $0.000200) ---")
    print(f"Task Type:                 {r2.get('task_type')}")
    print(f"Complexity Score:          {r2.get('complexity_score')}/10")
    print(f"Pre-Request Cost Est.:     ${r2.get('pre_request_estimated_cost_usd'):.6f}")
    print(f"Actual Request Cost:       ${r2['usage']['total_cost_usd']:.6f}")
    print(f"Selected Tier & Model:     Tier {r2.get('final_tier')} ({r2.get('selected_model')})")
    reason2 = r2.get('routing_reason', '').encode('ascii', 'ignore').decode('ascii')
    print(f"Routing Reason:            {reason2}")

    print("\n==================================================================================")

if __name__ == "__main__":
    asyncio.run(verify())
