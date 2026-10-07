"""PreCog persistent cognitive substrate reference implementation."""
from .adapters import (EmbeddingAdapter, ExtractionAdapter, MockModelAdapter, ModelAdapterError, OpenAICompatibleHTTPAdapter, PredictionAdapter, ProviderHTTPError, ProviderMalformedResponse, ProviderTimeout, RCAAdapter, ReflectionAdapter, RerankingAdapter, RetryPolicy, SummarizationAdapter)
from .embeddings import EmbeddingProvider, EmbeddingRecord, DeterministicEmbeddingProvider, build_embedding, is_embedding_current
from .models import Behavior, Experience, Knowledge, Memory, MemoryLifecycle, MemoryType, Relation, RelationType, RetrievalEvidence, Trajectory
from .store import InMemoryStore
from .postgres import PostgresStore
from .retrieval import HybridRetriever, LexicalRetriever, SemanticRetriever, RetrievalReranker
from .consolidation import Consolidator, ConsolidationProposal
from .dreaming import Dreamer, DreamReport
from .prediction import BehaviorPredictor, BehaviorPrediction
from .capability import CapabilityCandidate, CapabilityValidator
from .evaluation import EvaluationReport, Evaluator
from .contract import DataClass, FieldPolicy, PrivacyPolicy, validate_migration_version, validate_temporal_interval
from .trajectory import reconstruct_trajectory, validate_experience_temporal_order
from .relations import RelationGraph
from .ranker import BehaviorRanker, JevRankerAdapter
from .next_action import BestNextAction, BestNextActionSelector
from .evolution import CapabilityEvolution, EvolutionDecision, Manager, Healer, Judge
from .continual import ChampionChallenger, ModelCandidate, PromotionDecision

__all__ = [
    "EmbeddingAdapter","ExtractionAdapter","MockModelAdapter","ModelAdapterError","OpenAICompatibleHTTPAdapter","PredictionAdapter","ProviderHTTPError","ProviderMalformedResponse","ProviderTimeout","RCAAdapter","ReflectionAdapter","RerankingAdapter","RetryPolicy","SummarizationAdapter",
    "EmbeddingProvider","EmbeddingRecord","DeterministicEmbeddingProvider","build_embedding","is_embedding_current",
    "Behavior","Experience","Knowledge","Memory","MemoryLifecycle","MemoryType",
    "Relation","RelationType","RetrievalEvidence","Trajectory","InMemoryStore","PostgresStore",
    "HybridRetriever","LexicalRetriever","SemanticRetriever","RetrievalReranker","Consolidator","ConsolidationProposal","Dreamer","DreamReport",
    "BehaviorPredictor","BehaviorPrediction","CapabilityCandidate","CapabilityValidator",
    "EvaluationReport","Evaluator","DataClass","FieldPolicy","PrivacyPolicy",
    "validate_migration_version","validate_temporal_interval","reconstruct_trajectory",
    "validate_experience_temporal_order","RelationGraph","BehaviorRanker","JevRankerAdapter",
    "BestNextAction","BestNextActionSelector","CapabilityEvolution","EvolutionDecision",
    "Manager","Healer","Judge","ChampionChallenger","ModelCandidate","PromotionDecision",
]
