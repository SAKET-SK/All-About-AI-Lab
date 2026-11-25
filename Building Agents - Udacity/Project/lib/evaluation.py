import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from lib.agents import AgentState
from lib.state_machine import Run
from lib.llm import LLM
from lib.messages import AIMessage, BaseMessage
from lib.parsers import PydanticOutputParser


class TaskCompletionMetrics(BaseModel):
    """Metrics for task completion evaluation"""
    task_completed: bool = Field(description="Whether the task was completed successfully")
    steps_taken: int = Field(description="Number of steps taken to complete the task")
    expected_steps: Optional[int] = Field(description="Expected number of steps", default=None)


class QualityControlMetrics(BaseModel):
    """Metrics for quality control evaluation"""
    format_correct: bool = Field(description="Whether output format is correct")
    instructions_followed: bool = Field(description="Whether prompt instructions were followed")

class ToolInteractionMetrics(BaseModel):
    """Metrics for tool interaction evaluation"""
    correct_tool_selected: bool = Field(description="Whether the right tool was chosen")
    valid_arguments: bool = Field(description="Whether tool arguments were valid")
    tool_result_useful: bool = Field(description="Whether tool returned useful results")

class SystemMetrics(BaseModel):
    """System performance metrics"""
    total_tokens: int = Field(description="Total tokens used")
    execution_time: float = Field(description="Total execution time in seconds")
    tool_call_latency: float = Field(description="Average tool call latency")
    memory_usage: Optional[float] = Field(description="Memory usage if tracked", default=None)
    cost_estimate: Optional[float] = Field(description="Estimated cost in USD", default=None)

class EvaluationResult(BaseModel):
    """Complete evaluation result"""
    task_completion: TaskCompletionMetrics
    quality_control: QualityControlMetrics
    tool_interaction: ToolInteractionMetrics
    system_metrics: SystemMetrics
    overall_score: float = Field(description="Overall evaluation score (0-1)", ge=0, le=1)
    feedback: str = Field(description="Detailed feedback and recommendations")

class TestCase(BaseModel):
    """A test case for agent evaluation"""
    id: str
    description: str
    user_query: str
    expected_tools: List[str]
    reference_answer: Optional[str] = None
    max_steps: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class JudgeEvaluation(BaseModel):
    """Structured evaluation from LLM judge"""
    task_completed: bool = Field(description="Whether the task was completed successfully")
    format_correct: bool = Field(description="Whether output format is correct")
    instructions_followed: bool = Field(description="Whether prompt instructions were followed")
    explanation: str = Field(description="Brief explanation of the evaluation")

class AgentEvaluator:
    """Comprehensive agent evaluation framework"""
    
    def __init__(self):
        self.llm_judge = LLM(model="gpt-4o-mini")
    
    def evaluate_final_response(self, 
                          test_case: TestCase, 
                          agent_response: str,
                          execution_time: float,
                          total_tokens: int) -> EvaluationResult:
        """
        Evaluate the final response from the agent (black box approach)
        """
        # Use LLM as judge to evaluate the response
        judge_prompt = f"""
        Evaluate this agent response for the given task:
        
        Task: {test_case.description}
        User Query: {test_case.user_query}
        Agent Response: {agent_response}
        Reference Answer: {test_case.reference_answer or "No reference provided"}
        
        Rate the response on:
        1. Task completion: Did it fully answer the query?
        2. Format correctness: Is the format appropriate?
        3. Instruction following: Did it follow implicit instructions?
        
        Provide your evaluation with a brief explanation.
        """
        
        # Use structured output with Pydantic model
        judge_response = self.llm_judge.invoke(
            input=judge_prompt, 
            response_format=JudgeEvaluation
        )
        
        # Parse the structured response
        parser = PydanticOutputParser(model_class=JudgeEvaluation)
        try:
            evaluation = parser.parse(judge_response)
        except Exception as e:
            print(f"Debug: Structured parsing error: {e}")
            print(f"Debug: Judge response content: {judge_response.content}")
            
            # Fallback evaluation based on simple heuristics
            has_game_info = any(keyword in agent_response.lower() 
                            for keyword in ["zelda", "breath of the wild", "score", "98", "best"])
            
            evaluation = JudgeEvaluation(
                task_completed=has_game_info,
                format_correct=len(agent_response.strip()) > 0,
                instructions_followed=has_game_info,
                explanation=f"Fallback evaluation due to parsing error: {str(e)}"
            )
        
        # Calculate scores using the structured evaluation
        task_completion = TaskCompletionMetrics(
            task_completed=evaluation.task_completed,
            steps_taken=1,  # We don't track steps in final response evaluation
            expected_steps=test_case.max_steps
        )
        
        quality_control = QualityControlMetrics(
            format_correct=evaluation.format_correct,
            instructions_followed=evaluation.instructions_followed
        )
        
        # For final response evaluation, we can't evaluate tool interaction details
        tool_interaction = ToolInteractionMetrics(
            correct_tool_selected=True,  # Assume correct if task completed
            valid_arguments=True,
            tool_result_useful=evaluation.task_completed
        )
        
        system_metrics = SystemMetrics(
            total_tokens=total_tokens,
            execution_time=execution_time,
            tool_call_latency=0.0,  # Not tracked in final response
            cost_estimate=self._estimate_cost(total_tokens)
        )
        
        # Calculate overall score
        scores = [
            1.0 if task_completion.task_completed else 0.0,
            1.0 if quality_control.format_correct else 0.0,
            1.0 if quality_control.instructions_followed else 0.0
        ]
        overall_score = sum(scores) / len(scores)
        
        return EvaluationResult(
            task_completion=task_completion,
            quality_control=quality_control,
            tool_interaction=tool_interaction,
            system_metrics=system_metrics,
            overall_score=overall_score,
            feedback=evaluation.explanation
        )
    
    def evaluate_single_step(self, 
                           agent_messages: List[BaseMessage],
                           expected_tool_calls: List[str]) -> EvaluationResult:
        """
        Evaluate a single step/decision made by the agent
        """
        # Find the last AI message with tool calls
        last_ai_message = None
        for msg in reversed(agent_messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                last_ai_message = msg
                break
        
        if not last_ai_message or not last_ai_message.tool_calls:
            # No tool calls made
            tool_interaction = ToolInteractionMetrics(
                correct_tool_selected=False,
                valid_arguments=False,
                tool_result_useful=False
            )
            overall_score = 0.0
            feedback = "No tool calls were made when expected"
        else:
            # Evaluate the tool calls
            actual_tools = [tc.function.name for tc in last_ai_message.tool_calls]
            
            correct_tool_selected = any(tool in expected_tool_calls for tool in actual_tools)
            
            # Check if arguments are valid (basic check)
            valid_arguments = True
            try:
                for tc in last_ai_message.tool_calls:
                    json.loads(tc.function.arguments)
            except:
                valid_arguments = False
            
            tool_interaction = ToolInteractionMetrics(
                correct_tool_selected=correct_tool_selected,
                valid_arguments=valid_arguments,
                tool_result_useful=correct_tool_selected  # Assume useful if correct tool
            )
            
            overall_score = sum([
                1.0 if correct_tool_selected else 0.0,
                1.0 if valid_arguments else 0.0,
                1.0 if correct_tool_selected else 0.0
            ]) / 3.0
            
            feedback = f"Selected tools: {actual_tools}, Expected: {expected_tool_calls}"
        
        # Basic metrics for single step
        task_completion = TaskCompletionMetrics(
            task_completed=tool_interaction.correct_tool_selected,
            steps_taken=1
        )
        
        quality_control = QualityControlMetrics(
            format_correct=True,  # Assume format is correct if we got here
            instructions_followed=tool_interaction.correct_tool_selected
        )
        
        system_metrics = SystemMetrics(
            total_tokens=0,  # Not tracked in single step
            execution_time=0.0,
            tool_call_latency=0.0
        )
        
        return EvaluationResult(
            task_completion=task_completion,
            quality_control=quality_control,
            tool_interaction=tool_interaction,
            system_metrics=system_metrics,
            overall_score=overall_score,
            feedback=feedback
        )
    
    def evaluate_trajectory(self, 
                          test_case: TestCase,
                          run: Run) -> EvaluationResult:
        """
        Evaluate the entire trajectory/path taken by the agent
        """
        if not run.snapshots:
            return self._create_failed_evaluation("No execution snapshots found")
        
        final_state:AgentState = run.get_final_state()
        if not final_state:
            return self._create_failed_evaluation("No final state found")
        
        # Analyze the trajectory
        actual_steps = [
            snapshot for snapshot in run.snapshots 
            if snapshot.step_id not in ["__entry__", "__termination__"]
        ]
        steps_taken = len(actual_steps)
        messages = final_state.get("messages", [])
        total_tokens = final_state.get("total_tokens", 0)
        
        # Count tool calls in the trajectory
        tool_calls_made = []
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_calls_made.extend([tc.function.name for tc in msg.tool_calls])
        
        # Evaluate task completion
        expected_tools_used = any(tool in tool_calls_made for tool in test_case.expected_tools)
        within_step_limit = test_case.max_steps is None or steps_taken <= test_case.max_steps
        
        task_completion = TaskCompletionMetrics(
            task_completed=expected_tools_used and within_step_limit,
            steps_taken=steps_taken,
            expected_steps=test_case.max_steps
        )
        
        # Evaluate tool interactions
        correct_tools_used = set(tool_calls_made).intersection(set(test_case.expected_tools))
        tool_interaction = ToolInteractionMetrics(
            correct_tool_selected=len(correct_tools_used) > 0,
            valid_arguments=True,  # Assume valid if execution completed
            tool_result_useful=len(correct_tools_used) > 0
        )
        
        # Quality control - check if we have a final response
        has_final_response = any(isinstance(msg, AIMessage) and msg.content 
                               for msg in messages)
        
        quality_control = QualityControlMetrics(
            format_correct=has_final_response,
            instructions_followed=expected_tools_used
        )
        
        # System metrics
        execution_time = 0.0
        if run.end_timestamp and run.start_timestamp:
            execution_time = (run.end_timestamp - run.start_timestamp).total_seconds()
        
        system_metrics = SystemMetrics(
            total_tokens=total_tokens,
            execution_time=execution_time,
            tool_call_latency=execution_time / max(len(tool_calls_made), 1),
            cost_estimate=self._estimate_cost(total_tokens)
        )
        
        # Calculate overall score
        scores = [
            1.0 if task_completion.task_completed else 0.0,
            1.0 if quality_control.format_correct else 0.0,
            1.0 if quality_control.instructions_followed else 0.0,
            1.0 if tool_interaction.correct_tool_selected else 0.0
        ]
        overall_score = sum(scores) / len(scores)
        
        feedback = f"Trajectory: {steps_taken} steps, Tools used: {tool_calls_made}, Expected: {test_case.expected_tools}"
        
        return EvaluationResult(
            task_completion=task_completion,
            quality_control=quality_control,
            tool_interaction=tool_interaction,
            system_metrics=system_metrics,
            overall_score=overall_score,
            feedback=feedback
        )
    
    def _estimate_cost(self, total_tokens: int) -> float:
        """Estimate cost based on token usage (rough estimate for GPT-4o-mini)"""
        # Rough estimate: $0.15 per 1M input tokens, $0.60 per 1M output tokens
        # Assuming 50/50 split for simplicity
        cost_per_token = (0.15 + 0.60) / 2 / 1_000_000
        return total_tokens * cost_per_token
    
    def _create_failed_evaluation(self, reason: str) -> EvaluationResult:
        """Create a failed evaluation result"""
        return EvaluationResult(
            task_completion=TaskCompletionMetrics(task_completed=False, steps_taken=0),
            quality_control=QualityControlMetrics(format_correct=False, instructions_followed=False),
            tool_interaction=ToolInteractionMetrics(correct_tool_selected=False, valid_arguments=False, tool_result_useful=False),
            system_metrics=SystemMetrics(total_tokens=0, execution_time=0.0, tool_call_latency=0.0),
            overall_score=0.0,
            feedback=reason
        )
