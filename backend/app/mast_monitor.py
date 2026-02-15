import os
import json
import logging
from typing import List, Dict, Any, Optional
from .schemas import MASTReport, MASTFailureMode
import anthropic

logger = logging.getLogger(__name__)

class MASTMonitor:
    """
    MAST Integration: Runtime Robustness & Self-Correction
    Monitors agent traces for failure modes defined in the 
    Multi-Agent Systems Failure Taxonomy.
    """
    
    def __init__(self, client: Optional[Any] = None):
        self.client = client
        if not self.client:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze_trace(self, agent_trace: List[Dict[str, Any]]) -> MASTReport:
        """
        Analyzes a sequence of agent interactions for failures.
        """
        if not self.client:
            return MASTReport(
                detected_failures=[],
                critique="MAST Monitor inactive (no LLM)",
                agent_trace=agent_trace
            )

        prompt = f"""Analyze the following Multi-Agent interaction trace for failure modes.
        
Trace:
{json.dumps(agent_trace, indent=2)}

Failure Modes to check:
- FM-1.1: Disobey Task Specification (Agent ignored constraints)
- FM-1.2: Disobey Role Specification (Agent did work of another)
- FM-1.3: Step Repetition (Looping on same query/tool)
- FM-2.2: Fail to Ask for Clarification (Proceeded with 'Unknown')
- FM-2.4: Information Withholding (Didn't pass full evidence)
- FM-3.3: Incorrect Verification (Claims don't match data)

Return a JSON object following this schema:
{{
    "detected_failures": ["FM-X.X", ...],
    "critique": "Detailed explanation of why",
    "recovery_suggestion": "How to fix the next iteration"
}}
"""

        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            json_str = content[content.find("{") : content.rfind("}") + 1]
            result = json.loads(json_str)
            
            return MASTReport(
                detected_failures=[MASTFailureMode(f) for f in result.get("detected_failures", [])],
                critique=result.get("critique", ""),
                recovery_suggestion=result.get("recovery_suggestion"),
                agent_trace=agent_trace
            )
        except Exception as e:
            logger.error(f"MAST Analysis failed: {e}")
            return MASTReport(
                detected_failures=[],
                critique=f"Analysis error: {str(e)}",
                agent_trace=agent_trace
            )

    def detect_step_repetition(self, trace: List[Dict[str, Any]]) -> bool:
        """Heuristic-based repetition detection."""
        tool_calls = [t for t in trace if t.get("type") == "tool_call"]
        if len(tool_calls) < 2:
            return False
        
        last_call = tool_calls[-1]
        for prev_call in tool_calls[:-1]:
            if (prev_call.get("tool") == last_call.get("tool") and 
                prev_call.get("params") == last_call.get("params")):
                return True
        return False
