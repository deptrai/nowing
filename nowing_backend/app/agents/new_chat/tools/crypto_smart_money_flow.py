"""Smart money flow wrapper tool.

Wraps the raw Nansen smart money data to provide Sankey-ready visualization data.
"""

from typing import Any
from langchain_core.tools import tool

from .nansen_smart_money import create_nansen_smart_money_tool


def create_smart_money_flow_tool():
    """Factory: get_smart_money_flow."""
    
    nansen_tool = create_nansen_smart_money_tool()

    @tool
    async def get_smart_money_flow(token_address: str) -> dict[str, Any]:
        """Get smart money flow visualized as a Sankey diagram.
        
        Transforms the raw Nansen smart money output into a structured format
        (nodes and links) representing 24h USD value flows, ready for UI display.
        
        Args:
            token_address: EVM token contract address (0x...).
            
        Returns:
            Dict containing 'nodes', 'links', 'net_flow_amount', 'currency',
            and 'source_domain', or an error dict.
        """
        # Call the underlying nansen tool to get raw wallet flows
        # Note: because it's wrapped by a tool decorator, we use ainvoke
        res = await nansen_tool.ainvoke({"token_address": token_address})
        
        if "error" in res:
            # Propagate error so orchestrator can handle it gracefully (e.g. rate limit fallback)
            return {
                "error": res["error"],
                "source_domain": res.get("source_domain", "nansen.ai"),
                "status": res.get("status")
            }
            
        wallets = res.get("smart_money_wallets", [])
        net_flow_usd = res.get("net_flow_24h_usd", 0.0)
        
        nodes_dict = {"Market": True}
        links = []
        
        for w in wallets:
            label = w.get("label", "Unknown")
            # If multiple wallets have the same label, we might want to aggregate them or just append
            # Sankey will sum multiple links with the same source/target
            flow = w.get("net_flow_usd", 0.0)
            if flow == 0:
                continue
                
            nodes_dict[label] = True
            
            # flow > 0 means wallet is accumulating (buying from Market)
            if flow > 0:
                links.append({
                    "source": "Market",
                    "target": label,
                    "value": flow
                })
            else:
                # flow < 0 means wallet is distributing (selling to Market)
                links.append({
                    "source": label,
                    "target": "Market",
                    "value": abs(flow)
                })
                
        nodes = [{"id": n} for n in nodes_dict.keys()]
        
        return {
            "source_domain": "nansen.ai",
            "nodes": nodes,
            "links": links,
            "net_flow_amount": net_flow_usd,
            "currency": "USD"
        }

    return get_smart_money_flow
