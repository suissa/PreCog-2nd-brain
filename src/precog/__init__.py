"""PreCog persistent cognitive substrate reference implementation."""
from .models import Behavior, Experience, Knowledge, Memory, MemoryLifecycle, MemoryType, Relation, RelationType, RetrievalEvidence, Trajectory
from .store import InMemoryStore
from .retrieval import HybridRetriever
from .consolidation import Consolidator, ConsolidationProposal
from .dreaming import Dreamer, DreamReport
from .prediction import BehaviorPredictor, BehaviorPrediction
from .capability import CapabilityCandidate, CapabilityValidator
from .evaluation import EvaluationReport, Evaluator

__all__ = [
    "Behavior","Experience","Knowledge","Memory","MemoryLifecycle","MemoryType",
    "Relation","RelationType","RetrievalEvidence","Trajectory","InMemoryStore",
    "HybridRetriever","Consolidator","ConsolidationProposal","Dreamer","DreamReport",
    "BehaviorPredictor","BehaviorPrediction","CapabilityCandidate","CapabilityValidator",
    "EvaluationReport","Evaluator",
]
