"""PreCog persistent cognitive substrate reference implementation."""
from .adapters import (EmbeddingAdapter, ExtractionAdapter, MockModelAdapter, ModelAdapterError, OpenAICompatibleHTTPAdapter, PredictionAdapter, ProviderHTTPError, ProviderMalformedResponse, ProviderTimeout, RCAAdapter, ReflectionAdapter, RerankingAdapter, RetryPolicy, SummarizationAdapter)
from .embeddings import EmbeddingProvider, EmbeddingRecord, DeterministicEmbeddingProvider, build_embedding, is_embedding_current
from .models import Behavior, Experience, Knowledge, Memory, MemoryLifecycle, MemoryType, Relation, RelationType, RetrievalEvidence, Trajectory
from .store import InMemoryStore
from .postgres import PostgresStore
from .postgres_promotion_audit import PostgresPromotionAuditLog
from .audit_integrity import PromotionAuditIntegrityReport, calculate_event_hash
from .retrieval import HybridRetriever
from .retrieval_repository import RetrievalRepository, InMemoryRetrievalRepository, PostgresRetrievalRepository
from .consolidation import Consolidator, ConsolidationProposal
from .dreaming import Dreamer, DreamReport
from .prediction import BehaviorPredictor, BehaviorPrediction
from .capability import CapabilityCandidate, CapabilityValidator
from .evaluation import EvaluationReport, Evaluator
from .outcome_evaluation import OutcomeEvaluator, OutcomeEvaluationReport, PredictionObservation
from .contract import DataClass, FieldPolicy, PrivacyPolicy, validate_migration_version, validate_temporal_interval
from .trajectory import reconstruct_trajectory, validate_experience_temporal_order
from .relations import RelationGraph
from .projection import MarkdownProjection, MarkdownProjector, ProjectionError, project_knowledge, project_memory
from .ranker import BehaviorRanker, JevRankerAdapter
from .next_action import BestNextAction, BestNextActionSelector
from .feedback import ExecutionFeedbackRecorder, ExecutionResult, RecordedExecution
from .evolution import CapabilityEvolution, EvolutionDecision, Manager, Healer, Judge
from .continual import ChampionChallenger, ModelCandidate, PromotionDecision, OutcomePromotionDecision, outcome_quality
from .promotion_audit import InMemoryPromotionAuditLog, PromotionAuditEvent, PromotionAuditRecorder, PromotionAuditWriter

__all__ = [
    "EmbeddingAdapter","ExtractionAdapter","MockModelAdapter","ModelAdapterError","OpenAICompatibleHTTPAdapter","PredictionAdapter","ProviderHTTPError","ProviderMalformedResponse","ProviderTimeout","RCAAdapter","ReflectionAdapter","RerankingAdapter","RetryPolicy","SummarizationAdapter",
    "EmbeddingProvider","EmbeddingRecord","DeterministicEmbeddingProvider","build_embedding","is_embedding_current",
    "Behavior","Experience","Knowledge","Memory","MemoryLifecycle","MemoryType",
    "Relation","RelationType","RetrievalEvidence","Trajectory","InMemoryStore","PostgresStore","PostgresPromotionAuditLog",
    "HybridRetriever","RetrievalRepository","InMemoryRetrievalRepository","PostgresRetrievalRepository","Consolidator","ConsolidationProposal","Dreamer","DreamReport",
    "BehaviorPredictor","BehaviorPrediction","CapabilityCandidate","CapabilityValidator",
    "EvaluationReport","Evaluator","OutcomeEvaluator","OutcomeEvaluationReport","PredictionObservation","DataClass","FieldPolicy","PrivacyPolicy",
    "validate_migration_version","validate_temporal_interval","reconstruct_trajectory",
    "validate_experience_temporal_order","RelationGraph","BehaviorRanker","JevRankerAdapter",
    "BestNextAction","BestNextActionSelector","ExecutionFeedbackRecorder","ExecutionResult","RecordedExecution","CapabilityEvolution","EvolutionDecision",
    "Manager","Healer","Judge","ChampionChallenger","ModelCandidate","PromotionDecision","OutcomePromotionDecision","outcome_quality",
    "InMemoryPromotionAuditLog","PromotionAuditEvent","PromotionAuditRecorder","PromotionAuditWriter",
    "PromotionAuditIntegrityReport","calculate_event_hash",
    "MarkdownProjection","MarkdownProjector","ProjectionError","project_knowledge","project_memory",
]
