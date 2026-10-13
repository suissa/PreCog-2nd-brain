from datetime import datetime, timedelta, timezone
import pytest
from precog.models import Experience, Knowledge, Memory, MemoryType, Provenance, Relation, RelationType
from precog.relations import RelationGraph
from precog.store import InMemoryStore

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)

def setup_store():
    store = InMemoryStore()
    for i in ("e1", "e2", "e3"):
        store.append_experience(Experience(i, "t1", NOW, NOW, "actor", "event", {}, Provenance((i,), "capture")))
    return store

@pytest.mark.parametrize("kind", list(RelationType))
def test_each_relation_type_can_be_created(kind):
    store = setup_store()
    relation = Relation("r1", "e1", "e2", kind, 0.9, NOW, provenance=Provenance(("e1",), "test"))
    store.put_relation(relation)
    assert store.relations() == (relation,)

def test_orphan_endpoint_and_provenance_are_rejected():
    store = setup_store()
    with pytest.raises(ValueError, match="endpoints"):
        store.put_relation(Relation("r1", "e1", "missing", RelationType.SUPPORTS, 0.9, NOW, provenance=Provenance(("e1",), "test")))
    with pytest.raises(ValueError, match="provenance"):
        store.put_relation(Relation("r2", "e1", "e2", RelationType.SUPPORTS, 0.9, NOW, provenance=Provenance(("missing",), "test")))

def test_bounded_traversal_returns_edges_and_provenance():
    store = setup_store()
    for rid, source, target in (("r1","e1","e2"), ("r2","e2","e3")):
        store.put_relation(Relation(rid, source, target, RelationType.SUPPORTS, 0.9, NOW, provenance=Provenance((source,), "test")))
    graph = RelationGraph(store)
    assert len(graph.traverse("e1", max_depth=1)) == 1
    paths = graph.traverse("e1", max_depth=2)
    assert len(paths) == 2
    assert paths[-1].edges[-1].provenance.source_ids == ("e2",)

def test_acyclic_relation_rejects_cycle_but_supports_cycle_is_allowed():
    store = setup_store()
    store.put_relation(Relation("r1", "e1", "e2", RelationType.DERIVED_FROM, 1.0, NOW, provenance=Provenance(("e1",), "test")))
    store.put_relation(Relation("r2", "e2", "e3", RelationType.DERIVED_FROM, 1.0, NOW, provenance=Provenance(("e2",), "test")))
    with pytest.raises(ValueError, match="cycle"):
        store.put_relation(Relation("r3", "e3", "e1", RelationType.DERIVED_FROM, 1.0, NOW, provenance=Provenance(("e3",), "test")))
    store.put_relation(Relation("r4", "e1", "e2", RelationType.SUPPORTS, 1.0, NOW, provenance=Provenance(("e1",), "test")))
    store.put_relation(Relation("r5", "e2", "e1", RelationType.SUPPORTS, 1.0, NOW, provenance=Provenance(("e2",), "test")))
    assert len(store.relations()) == 4

def test_relation_deletion_is_audited():
    store = setup_store()
    relation = Relation("r1", "e1", "e2", RelationType.SUPPORTS, 1.0, NOW, provenance=Provenance(("e1",), "test"))
    store.put_relation(relation)
    store.delete_relation("r1", deleted_at=NOW + timedelta(seconds=1))
    assert not store.relations()
    assert store.relation_deletion_audit() == ((relation, NOW + timedelta(seconds=1)),)
