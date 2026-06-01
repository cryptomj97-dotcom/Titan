import json
from typing import Callable, Dict, Type

from services.agents.llm import LLMClient
from services.agents.output_schemas import BearOutput, BullOutput, JudgeOutput
from services.agents.state import TitanState


class DebateNode:
    def __init__(self) -> None:
        self.llm_client = LLMClient()

    def _safe_strength(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _serialize_context(self, state: TitanState) -> Dict[str, object]:
        return {
            "asset": state.asset,
            "asset_class": state.asset_class,
            "mode": state.mode,
            "regime": state.regime,
            "clusters": state.clusters,
            "confidence_score": state.confidence_score,
            "anomaly_result": state.anomaly_result,
            "gate_result": state.gate_result,
        }

    def _schema_definition(self, schema: Type[object]) -> str:
        fields = []
        for field_name, field_info in schema.__fields__.items():
            field_type = getattr(field_info.outer_type_, "__name__", str(field_info.outer_type_))
            fields.append(f"- {field_name}: {field_type}")
        return "\n".join(fields)

    def _build_prompt(self, state: TitanState, agent_role: str, schema: Type[object]) -> str:
        context = self._serialize_context(state)
        schema_spec = self._schema_definition(schema)

        return (
            f"You are the {agent_role} agent for Titan, a structured quantitative decision engine. "
            "Use only the provided context, do not hallucinate external events, and format the response as valid JSON. "
            "Respect the schema precisely.\n\n"
            f"Context:\n{json.dumps(context, indent=2, default=str)}\n\n"
            f"Schema:\n{schema_spec}\n\n"
            "Output only the JSON object."
        )

    def _generate_agent_output(self, state: TitanState, role: str, schema: Type[object]) -> object:
        user_prompt = self._build_prompt(state, role, schema)
        system_prompt = (
            "You are a structured debate agent. Return ONLY a JSON object matching the requested schema. "
            "If the model cannot answer, return the closest valid JSON object with default values."
        )
        return self.llm_client.generate(system_prompt, user_prompt, schema, temperature=0.0, max_tokens=400)

    def _build_bull(self, state: TitanState) -> BullOutput:
        confidence = self._safe_strength(state.confidence_score.get("confidence", 0.0))
        consensus = state.confidence_score.get("cluster_consensus", "NEUTRAL")
        regime = state.regime["consensus"].get("consensus_regime", "UNKNOWN")
        evidence = [
            f"Cluster consensus is {consensus}, with strength {state.confidence_score.get('cluster_strength', 0.0):.2f}",
            f"Regime detection favors {regime}, confidence {state.regime['consensus'].get('consensus_confidence', 0.0):.2f}",
        ]
        if state.confidence_score.get("backtest_edge", 0.0) > 0.0:
            evidence.append(f"Backtest edge is positive at {state.confidence_score['backtest_edge']:.3f}")

        downside_risks = []
        if state.anomaly_result.get("severity") in {"HIGH", "CRITICAL"}:
            downside_risks.append(f"Anomaly level is {state.anomaly_result['severity']}, which may reduce confidence.")
        if state.gate_result.get("is_blocked"):
            downside_risks.append("Pre-signal gate has identified a potential regime misalignment or low conviction.")
        if not downside_risks:
            downside_risks.append("Risks are controlled by the current regime and anomaly checks.")

        return BullOutput(
            summary=f"Quant signals and regime alignment support a {consensus.lower()} view for {state.asset}.",
            evidence=evidence,
            downside_risks=downside_risks,
            trade_bias=consensus,
            confidence=confidence,
            position_size=state.confidence_score.get("confidence", 0.0),
        )

    def _build_bear(self, state: TitanState) -> BearOutput:
        confidence = self._safe_strength(1.0 - state.confidence_score.get("confidence", 0.0))
        concerns = []
        invalidation_points = []

        if state.anomaly_result.get("severity") in {"HIGH", "CRITICAL"}:
            concerns.append(f"Market anomaly severity is {state.anomaly_result['severity']}, which elevates risk.")
            invalidation_points.append("A confirmed anomaly should invalidate the trade until conditions normalize.")

        if not state.regime["consensus"].get("agreement", True):
            concerns.append("Statistical and HMM regime signals are not fully aligned.")
            invalidation_points.append("A regime disagreement should prompt re-evaluation.")

        if state.confidence_score.get("signal") == "NEUTRAL":
            concerns.append("Overall signal confidence is too low for a clean trade.")
            invalidation_points.append("The system should remain flat until conviction improves.")

        if not concerns:
            concerns.append("The quantitative setup appears coherent, but trail conditions closely.")
            invalidation_points.append("If momentum reverses or volatility spikes, exit immediately.")

        evidence = [
            f"Regime consensus: {state.regime['consensus'].get('consensus_regime', 'UNKNOWN')}",
            f"Anomaly severity: {state.anomaly_result.get('severity', 'NORMAL')}",
        ]

        return BearOutput(
            summary="The current opportunity requires caution because risk factors are present.",
            concerns=concerns,
            invalidation_points=invalidation_points,
            conviction=confidence,
            evidence=evidence,
        )

    def _build_judge(self, state: TitanState, bull: BullOutput, bear: BearOutput) -> JudgeOutput:
        signal_confidence = state.confidence_score.get("confidence", 0.0)
        bull_score = int(max(0, min(100, 50 + signal_confidence * 50)))
        bear_score = int(max(0, min(100, 50 + (1.0 - signal_confidence) * 50)))

        if state.gate_result.get("is_blocked") or state.confidence_score.get("signal") == "NEUTRAL":
            verdict = "SIGNAL_REJECTED"
        elif signal_confidence >= 0.60:
            verdict = "SIGNAL_CONFIRMED"
        elif signal_confidence >= 0.40:
            verdict = "NEEDS_REVIEW"
        else:
            verdict = "SIGNAL_REJECTED"

        quant_alignment = {
            "bull": int(min(10, max(1, round(state.confidence_score.get("cluster_strength", 0.0) * 10)))),
            "bear": int(min(10, max(1, round((1.0 - state.confidence_score.get("cluster_strength", 0.0)) * 10)))),
        }

        risk_acknowledgment = {
            "bull": 8 if bull.downside_risks else 6,
            "bear": 9 if bear.concerns else 7,
        }

        return JudgeOutput(
            verdict=verdict,
            bull_score=bull_score,
            bear_score=bear_score,
            evidence_quality={"bull": 8, "bear": 7},
            logical_coherence={"bull": 8, "bear": 7},
            risk_acknowledgment=risk_acknowledgment,
            quant_alignment=quant_alignment,
            key_risk=state.anomaly_result.get("severity", "NORMAL") if state.anomaly_result.get("severity") != "NORMAL" else "Regime disagreement or low conviction",
            rationale="The final judgement balances confidence, anomaly status, cluster consensus, and regime alignment.",
            position_modifier=signal_confidence,
        )

    def execute(self, state: TitanState, publish: Callable[[str, dict], None]) -> TitanState:
        bull = None
        bear = None
        judge = None

        if self.llm_client.is_configured:
            try:
                publish("DEBATE_LLM_STARTED", {"provider": self.llm_client.provider_name})
                bull = self._generate_agent_output(state, "Bull", BullOutput)
                bear = self._generate_agent_output(state, "Bear", BearOutput)
                judge = self._generate_agent_output(state, "Judge", JudgeOutput)
                publish("DEBATE_LLM_COMPLETED", {"provider": self.llm_client.provider_name})
            except Exception as exc:
                publish("DEBATE_LLM_FAILED", {"error": str(exc)})

        if bull is None or bear is None or judge is None:
            bull = self._build_bull(state)
            bear = self._build_bear(state)
            judge = self._build_judge(state, bull, bear)
            publish("DEBATE_RULE_BASED", {"reason": "LLM unavailable or failed, falling back to rule-based structured output."})

        state.debate = {
            "bull": bull.dict(),
            "bear": bear.dict(),
            "judge": judge.dict(),
        }

        publish("DEBATE_READY", state.debate)
        return state
