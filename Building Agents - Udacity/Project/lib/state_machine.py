from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, Generic, cast, Type, TypedDict, get_type_hints
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import copy
import inspect


StateSchema = TypeVar("StateSchema")

@dataclass
class Resource:
    vars: Dict[str, Any]

class Step(Generic[StateSchema]):
    def __init__(self, step_id: str, logic: Callable[[StateSchema], Dict]):
        self.step_id = step_id
        self.logic = logic
        # Store the number of parameters the logic function expects
        self.logic_params_count = self._calculate_params_count()

    def __str__(self) -> str:
        return f"Step('{self.step_id}')"

    def __repr__(self) -> str:
        return self.__str__()

    def _calculate_params_count(self):
        """Calculate the number of parameters excluding 'self' for bound methods"""
        if inspect.ismethod(self.logic):
            # For bound methods, subtract 1 to exclude 'self'
            return self.logic.__func__.__code__.co_argcount - 1
        else:
            # For regular functions
            return self.logic.__code__.co_argcount

    def run(self, state: StateSchema, state_schema: Type[StateSchema], resource: Resource=None) -> StateSchema:
        # Call logic function with appropriate number of arguments
        if self.logic_params_count == 1:
            result = self.logic(state)
        elif self.logic_params_count == 2:
            result = self.logic(state, resource)
        else:
            raise ValueError(
                f"Step '{self.step_id}' logic function must accept either 1 argument (state) "
                f"or 2 arguments (state, resource). Found {self.logic_params_count} arguments."
            ) 
        # Get expected fields from the TypedDict
        expected_fields = get_type_hints(state_schema)
        
        # Create new state with all fields from state_schema
        # Only copy fields that are defined in state_schema
        updated = {**state}
        for field, value in result.items():
            if field in expected_fields:
                updated[field] = value
        
        return cast(StateSchema, updated)


class EntryPoint(Step[StateSchema]):
    """Special step that marks the beginning of the workflow.
    Users should connect this step to their first business logic step."""
    def __init__(self):
        super().__init__("__entry__", lambda x: {})


class Termination(Step[StateSchema]):
    """Special step that marks the end of the workflow.
    Users should connect their final business logic step(s) to this step."""
    def __init__(self):
        super().__init__("__termination__", lambda x: {})


@dataclass
class Transition(Generic[StateSchema]):
    source: str
    targets: List[str]
    condition: Optional[Callable[[StateSchema], Union[str, List[str], Step[StateSchema], List[Step[StateSchema]]]]] = None

    def __str__(self) -> str:
        return f"Transition('{self.source}' -> {self.targets})"

    def __repr__(self) -> str:
        return self.__str__()

    def resolve(self, state: StateSchema) -> List[str]:
        if self.condition:
            result = self.condition(state)
            if isinstance(result, Step):
                return [result.step_id]
            elif isinstance(result, list) and all(isinstance(x, Step) for x in result):
                return [step.step_id for step in result]
            elif isinstance(result, str):
                return [result]
            return result
        return self.targets


@dataclass
class Snapshot(Generic[StateSchema]):
    """Represents a single state snapshot in time"""
    snapshot_id: str
    timestamp: datetime
    state_data: StateSchema
    state_schema: Type[StateSchema]
    step_id: str

    def __str__(self) -> str:
        return f"Snapshot('{self.snapshot_id}') @ [{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')}]: {self.step_id}.State({self.state_data})"

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def create(cls, state_data: StateSchema, state_schema: Type[StateSchema],
               step_id:str) -> 'Snapshot[StateSchema]':
        return cls(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            state_data=state_data,
            state_schema=state_schema,
            step_id=step_id,
        )


@dataclass
class Run(Generic[StateSchema]):
    """Represents a single execution run of the state machine"""
    run_id: str
    start_timestamp: datetime
    snapshots: List[Snapshot[StateSchema]] = field(default_factory=list)
    end_timestamp: Optional[datetime] = None

    def __str__(self) -> str:
        return f"Run('{self.run_id}')"

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def create(cls) -> 'Run[StateSchema]':
        return cls(
            run_id=str(uuid.uuid4()),
            start_timestamp=datetime.now()
        )

    @property
    def metadata(self) -> Dict:
        return {
            "run_id": self.run_id,
            "start_timestamp": self.start_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "end_timestamp": self.end_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "snapshot_counts": len(self.snapshots)
        }

    def add_snapshot(self, snapshot: Snapshot[StateSchema]):
        """Add a new snapshot to this run"""
        self.snapshots.append(snapshot)

    def complete(self):
        """Mark this run as complete"""
        self.end_timestamp = datetime.now()

    def get_final_state(self) -> Optional[StateSchema]:
        """Get the final state of this run"""
        if not self.snapshots:
            return None
        return self.snapshots[-1].state_data


class StateMachine(Generic[StateSchema]):
    def __init__(self, state_schema: Type[StateSchema]):
        self.state_schema = state_schema
        self.steps: Dict[str, Step[StateSchema]] = {}
        self.transitions: Dict[str, List[Transition[StateSchema]]] = {}

    def __str__(self) -> str:
        schema_keys = list(get_type_hints(self.state_schema).keys())
        return f"StateMachine(schema={schema_keys})"

    def __repr__(self) -> str:
        return self.__str__()

    def add_steps(self, steps: List[Step[StateSchema]]):
        """Add steps to the workflow"""
        for step in steps:
            self.steps[step.step_id] = step

    def connect(
        self,
        source: Union[Step[StateSchema], str],
        targets: Union[Step[StateSchema], str, List[Union[Step[StateSchema], str]]],
        condition: Optional[Callable[[StateSchema], Union[str, List[str]]]] = None
    ):
        src_id = source.step_id if isinstance(source, Step) else source
        target_list = targets if isinstance(targets, list) else [targets]
        target_ids = [t.step_id if isinstance(t, Step) else t for t in target_list]
        transition = Transition[StateSchema](source=src_id, targets=target_ids, condition=condition)
        if src_id not in self.transitions:
            self.transitions[src_id] = []
        self.transitions[src_id].append(transition)

    def run(self, state: StateSchema, resource: Resource = None):
        # Validate that state has at least one field from the schema
        expected_fields = get_type_hints(self.state_schema)
        state_fields = set(state.keys())
        common_fields = state_fields.intersection(expected_fields)
        
        if not common_fields:
            raise ValueError(f"Initial state must have at least one field from the schema. Expected fields: {list(expected_fields.keys())}")

        entry_points = [s for s in self.steps.values() if isinstance(s, EntryPoint)]
        if not entry_points:
            raise Exception("No EntryPoint step found in workflow")
        if len(entry_points) > 1:
            raise Exception("Multiple EntryPoint steps found in workflow")
        
        # Create a new run for this execution
        current_run = Run.create()
        
        current_step_id = entry_points[0].step_id        

        while current_step_id:
            step = self.steps[current_step_id]
            if isinstance(step, Termination):
                print(f"[StateMachine] Terminating: {current_step_id}")
                break
            
            # Replace state entirely
            state = step.run(state, self.state_schema, resource)  

            if isinstance(step, EntryPoint):
                print(f"[StateMachine] Starting: {current_step_id}")
            else:
                print(f"[StateMachine] Executing step: {current_step_id}")

            # Create and add snapshot to the current run
            snapshot = Snapshot.create(copy.deepcopy(state), self.state_schema, current_step_id)
            current_run.add_snapshot(snapshot)

            transitions = self.transitions.get(current_step_id, [])
            next_steps: List[str] = []

            for t in transitions:
                next_steps += t.resolve(state)

            if not next_steps:
                raise Exception(f"[StateMachine] No transitions found from step: {current_step_id}")

            if len(next_steps) > 1:
                raise NotImplementedError("Parallel execution not implemented yet.")

            current_step_id = next_steps[0]

        current_run.complete()
        return current_run
