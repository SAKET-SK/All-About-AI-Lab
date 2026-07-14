from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from typing import Dict, List, Optional
import os

# RAGAS imports
try:
    from ragas import SingleTurnSample
    from ragas.metrics import (
        BleuScore,
        NonLLMContextPrecisionWithReference,
        ResponseRelevancy,
        Faithfulness,
        RougeScore,
    )
    from ragas import evaluate
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False


def evaluate_response_quality(
    question: str,
    answer: str,
    contexts: List[str],
    reference: Optional[str] = None,
) -> Dict[str, float]:
    """
    Evaluate response quality using RAGAS metrics.

    Args:
        question  : The user's original question.
        answer    : The LLM-generated answer.
        contexts  : List of retrieved document chunks used as context.
        reference : Expected / gold answer used for BLEU and ROUGE scoring.
                    When None, BLEU and ROUGE are skipped (not faked against self).

    Returns:
        Dict mapping metric name -> float score, or {"error": "..."} on failure.
    """
    if not RAGAS_AVAILABLE:
        return {"error": "RAGAS not available. Install with: pip install ragas"}

    # ── Guard: handle empty / malformed inputs ───────────────────────────────
    if not question or not isinstance(question, str):
        return {"error": "Invalid input: 'question' must be a non-empty string."}
    if not answer or not isinstance(answer, str):
        return {"error": "Invalid input: 'answer' must be a non-empty string."}
    if not contexts or not isinstance(contexts, list):
        return {"error": "Invalid input: 'contexts' must be a non-empty list of strings."}

    contexts = [c for c in contexts if isinstance(c, str) and c.strip()]
    if not contexts:
        return {"error": "Invalid input: 'contexts' contains no valid (non-empty) strings."}

    try:
        # TODO: Create evaluator LLM with model gpt-3.5-turbo
        evaluator_llm = LangchainLLMWrapper(
            ChatOpenAI(
                model="gpt-3.5-turbo",
                api_key=os.environ.get("CHROMA_OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")),
            )
        )

        # TODO: Create evaluator_embeddings with model text-embedding-3-small
        evaluator_embeddings = LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=os.environ.get("CHROMA_OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")),
            )
        )

        # TODO: Define an instance for each metric to evaluate
        # Required: ResponseRelevancy + Faithfulness (LLM-based, no reference needed)
        response_relevancy = ResponseRelevancy(
            llm=evaluator_llm,
            embeddings=evaluator_embeddings,
        )
        faithfulness = Faithfulness(llm=evaluator_llm)

        # TODO: Evaluate the response using the metrics
        # Build SingleTurnSample — reference is only set when a real gold answer exists.
        # BLEU and ROUGE MUST compare against a genuine reference, not the answer itself,
        # otherwise they trivially score 1.0 and produce meaningless results.
        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=reference,          # None when no gold answer is available
        )

        results: Dict[str, float] = {}

        # ── Always-run metrics (no reference required) ──────────────────────
        always_metrics = {
            "response_relevancy": response_relevancy,
            "faithfulness": faithfulness,
        }

        # ── Reference-dependent metrics (BLEU / ROUGE) ──────────────────────
        # Only included when a genuine reference answer is provided.
        reference_metrics: Dict[str, Any] = {}
        if reference and isinstance(reference, str) and reference.strip():
            reference_metrics = {
                "bleu_score": BleuScore(),
                "rouge_score": RougeScore(),
            }

        import asyncio

        # Score each metric individually so one failure doesn't crash everything
        for metric_name, metric in {**always_metrics, **reference_metrics}.items():
            try:
                score = asyncio.get_event_loop().run_until_complete(
                    metric.single_turn_ascore(sample)
                )
                results[metric_name] = round(float(score), 4)
            except Exception as metric_err:
                results[metric_name] = f"Error: {str(metric_err)}"

        # TODO: Return the evaluation results
        return results

    except Exception as e:
        return {"error": f"Evaluation pipeline failed: {str(e)}"}


# ── Batch evaluation helper (used by chat.py and CLI) ───────────────────────

def batch_evaluate(
    test_items: List[Dict],
    verbose: bool = True,
) -> Dict:
    """
    Run evaluate_response_quality over a list of pre-built
    {question, answer, contexts} dicts and return per-item + aggregate results.

    Args:
        test_items : list of dicts, each with keys: question, answer, contexts
        verbose    : print progress to stdout

    Returns:
        {
          "results"   : [per-item score dicts],
          "aggregate" : {metric: mean_score, ...}
        }
    """
    if not test_items:
        return {"error": "No test items provided for batch evaluation."}

    all_results = []
    metric_totals: Dict[str, List[float]] = {}

    for idx, item in enumerate(test_items, 1):
        if verbose:
            print(f"  Evaluating item {idx}/{len(test_items)}: {item.get('question', '')[:60]}")

        scores = evaluate_response_quality(
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            contexts=item.get("contexts", []),
            reference=item.get("reference"),   # real gold answer for BLEU/ROUGE
        )

        row = {"question": item.get("question", ""), **scores}
        all_results.append(row)

        for k, v in scores.items():
            if isinstance(v, float):
                metric_totals.setdefault(k, []).append(v)

    # Aggregate means
    aggregate = {
        metric: round(sum(vals) / len(vals), 4)
        for metric, vals in metric_totals.items()
        if vals
    }

    return {"results": all_results, "aggregate": aggregate}
