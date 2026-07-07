from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.state import AgentState
from app.agents.tools import TOOLS_BY_FEATURE, AgentTool


class AIServiceAgent:
    def __init__(self) -> None:
        self._graph = self._build_graph()

    def run(self, feature: str, payload: dict[str, Any]) -> dict[str, Any]:
        final_state = self._graph.invoke(
            {
                "feature": feature,
                "payload": payload,
                "status": "pending",
            }
        )
        if final_state.get("status") == "failed":
            error = final_state.get("error") or {
                "code": "AGENT_FAILED",
                "message": "AI agent execution failed.",
            }
            return {
                "success": False,
                "data": {},
                "error": error,
                "warnings": ["AI agent execution failed."],
                "agent": self._metadata(final_state),
            }

        result = final_state.get("result") or {}
        if not isinstance(result, dict):
            result = {"success": True, "data": result}

        result.setdefault("success", True)
        result["agent"] = self._metadata(final_state)
        return result

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("router", self._router_node)
        graph.add_node("error", self._error_node)

        for feature, tool in TOOLS_BY_FEATURE.items():
            graph.add_node(feature, self._tool_node(tool))

        graph.set_entry_point("router")
        graph.add_conditional_edges(
            "router",
            self._route_feature,
            {**{feature: feature for feature in TOOLS_BY_FEATURE}, "error": "error"},
        )
        for feature in TOOLS_BY_FEATURE:
            graph.add_edge(feature, END)
        graph.add_edge("error", END)
        return graph.compile()

    def _router_node(self, state: AgentState) -> AgentState:
        return {**state, "status": "running"}

    def _route_feature(self, state: AgentState) -> str:
        feature = state.get("feature")
        return str(feature) if feature in TOOLS_BY_FEATURE else "error"

    def _tool_node(self, tool: AgentTool):
        def invoke_tool(state: AgentState) -> AgentState:
            output = tool.invoke(state.get("payload") or {})
            if not output.get("success"):
                return {
                    **state,
                    "tool_name": tool.name,
                    "status": "failed",
                    "error": output.get("error") or {
                        "code": "TOOL_FAILED",
                        "message": f"{tool.name} failed.",
                    },
                }
            return {
                **state,
                "tool_name": tool.name,
                "status": "success",
                "result": output.get("result") or {},
            }

        return invoke_tool

    def _error_node(self, state: AgentState) -> AgentState:
        feature = state.get("feature")
        return {
            **state,
            "status": "failed",
            "error": {
                "code": "UNKNOWN_AGENT_FEATURE",
                "message": f"No AI agent tool is registered for feature '{feature}'.",
            },
        }

    def _metadata(self, state: AgentState) -> dict[str, Any]:
        return {
            "feature": state.get("feature"),
            "toolName": state.get("tool_name"),
            "status": state.get("status"),
            "graph": "hireos_ai_service_agent",
        }
