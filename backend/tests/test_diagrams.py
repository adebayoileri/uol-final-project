"""Tests for generated lesson diagrams.

The weight here is on the validator rather than the generator. A diagram is
produced by a small local model choosing from a menu of kinds, so the question
that decides whether the feature is any good is not "did it return JSON" but
"is what it returned drawable and true". Every rejection below corresponds to
something that would otherwise render as a plausible-looking wrong picture.

Stubs the module-local _call_ollama, the same approach as test_lesson_enrichment.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.diagram_spec import validate_diagrams
from app.main import app
from app.models import Course, Lesson, Module
from app.services.diagram_generator import _build_prompt, generate_diagrams
from tests.conftest import TEST_USER_ID

DIAGRAM_PATCH = "app.services.diagram_generator._call_ollama"

_LONG_DEF = (
    "It opens a path and returns a file object positioned at the start, "
    "holding an OS-level handle until it is closed."
)

LESSON_CONTENT = json.dumps({
    "key_concepts": [
        {"name": "open()", "definition": _LONG_DEF, "example": "f = open('d.txt')"},
        {"name": "read()", "definition": _LONG_DEF, "example": "text = f.read()"},
    ],
    "worked_example": "Step 1: open the file.\nStep 2: read it.\nStep 3: close it.",
    "common_pitfalls": ["Forgetting to close the file."],
    "practice_prompts": ["Why does close() matter?"],
})

BOARD = {
    "id": "knight-move",
    "kind": "board",
    "title": "How a knight moves",
    "caption": "From d4 a knight reaches eight squares.",
    "size": 8,
    "pieces": [{"at": "d4", "glyph": "N", "tone": "brand"}],
    "highlight": ["e6", "f5", "f3", "e2", "c2", "b3", "b5", "c6"],
}

GRAPH = {
    "id": "file-io",
    "kind": "graph",
    "title": "Reading a file",
    "caption": "Every read follows the same three stages.",
    "layout": "chain",
    "nodes": [
        {"id": "open", "label": "open(path)"},
        {"id": "read", "label": "read()"},
        {"id": "close", "label": "close()"},
    ],
    "edges": [
        {"from": "open", "to": "read"},
        {"from": "read", "to": "close"},
    ],
}

TREE = {
    "id": "bst",
    "kind": "graph",
    "title": "A binary search tree",
    "caption": "Every left child is smaller than its parent.",
    "layout": "tree",
    "nodes": [
        {"id": "n8", "label": "8"},
        {"id": "n3", "label": "3"},
        {"id": "n10", "label": "10"},
    ],
    "edges": [{"from": "n8", "to": "n3"}, {"from": "n8", "to": "n10"}],
}

PLOT = {
    "id": "sigmoid",
    "kind": "plot",
    "title": "The sigmoid",
    "caption": "It squashes any real number into the range zero to one.",
    "x_label": "z",
    "y_label": "sigma(z)",
    "x_range": [-6, 6],
    "y_range": [0, 1],
    "series": [
        {"id": "s1", "label": "sigma(z)", "type": "function",
         "fn": {"family": "sigmoid", "params": {"k": 1}}}
    ],
    "markers": [{"id": "m1", "at": [0, 0.5], "label": "midpoint"}],
}

GEOMETRY = {
    "id": "right-triangle",
    "kind": "geometry",
    "title": "A 3-4-5 triangle",
    "caption": "The sides 3, 4 and 5 always form a right angle.",
    "shape": "triangle",
    "sides": [3, 4, 5],
    "show_sides": True,
    "show_angles": True,
}


def _wrap(*diagrams) -> str:
    return json.dumps({"diagrams": list(diagrams)})


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_lesson(
    db_session,
    content_json: str | None = LESSON_CONTENT,
    *,
    chess: bool = False,
) -> Lesson:
    course = Course(
        user_id=TEST_USER_ID,
        goal="How to play chess" if chess else "Learn Python file handling",
        duration="short_term",
        category="Games" if chess else "Programming",
        title="Learning Chess Fundamentals" if chess else "Python Files",
        description="A short course.",
    )
    db_session.add(course)
    db_session.flush()

    module = Module(course_id=course.id, order_index=0, title="Basics", description="Basics.")
    db_session.add(module)
    db_session.flush()

    lesson = Lesson(
        module_id=module.id,
        order_index=0,
        title="Reading files",
        description="Content for open() and read().",
        duration_minutes=45,
        content_json=content_json,
    )
    db_session.add(lesson)
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# The four kinds are accepted at their happy path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "spec", [BOARD, GRAPH, TREE, PLOT, GEOMETRY],
    ids=["board", "graph-chain", "graph-tree", "plot", "geometry"],
)
def test_valid_specs_accepted(spec):
    out = validate_diagrams({"diagrams": [spec]})
    assert len(out) == 1
    assert out[0]["kind"] == spec["kind"]


def test_empty_list_is_valid():
    """Declining is a success, not a failure — most lessons need no diagram."""
    assert validate_diagrams({"diagrams": []}) == []


def test_missing_key_is_treated_as_empty():
    assert validate_diagrams({}) == []


def test_edge_from_alias_survives_the_round_trip():
    """`from` is a Python keyword; a lost alias would silently break every edge."""
    out = validate_diagrams({"diagrams": [GRAPH]})
    assert out[0]["edges"][0]["from"] == "open"
    assert "from_" not in out[0]["edges"][0]


def test_unknown_extra_keys_are_ignored_not_rejected():
    """Small models add stray keys; discarding a good diagram over one is worse."""
    spec = {**BOARD, "notes": "some commentary", "style": "modern"}
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


# ---------------------------------------------------------------------------
# Rejections — each of these would otherwise render as a wrong picture
# ---------------------------------------------------------------------------

def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        validate_diagrams({"diagrams": [{**BOARD, "kind": "sankey"}]})


def test_off_board_highlight_rejected():
    with pytest.raises(ValueError, match="off a 4x4 board"):
        validate_diagrams({"diagrams": [{**BOARD, "size": 4, "highlight": ["e6"]}]})


def test_off_board_piece_rejected():
    with pytest.raises(ValueError, match="off a 4x4 board"):
        validate_diagrams({"diagrams": [
            {**BOARD, "size": 4, "highlight": [], "pieces": [{"at": "h8", "glyph": "K"}]}
        ]})


def test_two_pieces_on_one_square_rejected():
    with pytest.raises(ValueError, match="two pieces"):
        validate_diagrams({"diagrams": [{
            **BOARD,
            "pieces": [{"at": "d4", "glyph": "N"}, {"at": "d4", "glyph": "K"}],
        }]})


# ---------------------------------------------------------------------------
# Piece reachability. Every case below is a legal square, so nothing structural
# rejects it — these exist because the live Chess course produced a bishop on
# e2 highlighting a1, h8, a8, h1 and f5, none of which are on a diagonal.
# ---------------------------------------------------------------------------

def test_bishop_off_its_diagonals_rejected():
    """The exact spec the live model produced. Drawable, plausible, and false."""
    spec = {
        **BOARD,
        "id": "bishop", "title": "How a bishop moves",
        "caption": "From e2 a bishop reaches these squares.",
        "pieces": [{"at": "e2", "glyph": "B", "tone": "brand"}],
        "highlight": ["a1", "h8", "a8", "h1", "c4", "f5"],
    }
    with pytest.raises(ValueError, match="unreachable"):
        validate_diagrams({"diagrams": [spec]})


def test_bishop_on_its_diagonals_accepted():
    spec = {
        **BOARD,
        "pieces": [{"at": "e2", "glyph": "B", "tone": "brand"}],
        "highlight": ["d1", "f1", "d3", "c4", "b5", "a6", "f3", "g4", "h5"],
    }
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_a_subset_of_legal_moves_is_fine():
    """Illustrating two of a knight's eight moves must not be rejected."""
    spec = {**BOARD, "highlight": ["e6", "c6"]}
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_rook_off_its_lines_rejected():
    spec = {
        **BOARD,
        "pieces": [{"at": "a1", "glyph": "R", "tone": "brand"}],
        "highlight": ["a8", "h1", "d4"],
    }
    with pytest.raises(ValueError, match="unreachable"):
        validate_diagrams({"diagrams": [spec]})


def test_unicode_glyphs_are_checked_too():
    spec = {
        **BOARD,
        "pieces": [{"at": "d4", "glyph": "♘", "tone": "brand"}],
        "highlight": ["d5"],
    }
    with pytest.raises(ValueError, match="unreachable"):
        validate_diagrams({"diagrams": [spec]})


def test_a_pieces_own_square_may_be_highlighted():
    spec = {**BOARD, "highlight": ["d4", "e6"]}
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_non_chess_glyphs_skip_the_check():
    """A board used as a coordinate grid or matrix must stay unconstrained."""
    spec = {
        **BOARD,
        "size": 4,
        "pieces": [{"at": "a1", "glyph": "x", "tone": "brand"}],
        "highlight": ["c3", "d4", "b2"],
    }
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_pawns_skip_the_check():
    """A pawn's move depends on colour and history, which is not knowable here."""
    spec = {
        **BOARD,
        "pieces": [{"at": "e2", "glyph": "P", "tone": "brand"}],
        "highlight": ["e3", "e4"],
    }
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_two_pieces_allow_the_union_of_their_moves():
    spec = {
        **BOARD,
        "pieces": [
            {"at": "d4", "glyph": "N", "tone": "brand"},
            {"at": "a1", "glyph": "R", "tone": "info"},
        ],
        "highlight": ["e6", "a8"],
    }
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


# ---------------------------------------------------------------------------
# Relevance, not just consistency. The live History-of-AI course cached a board
# with a knight on d4 against a lesson on the perceptron: every square legal,
# both highlights genuine knight moves, and completely unrelated to the subject.
# ---------------------------------------------------------------------------

class _FakeCourse:
    def __init__(self, goal="", category="", title=""):
        self.goal, self.category, self.title = goal, category, title


CHESS_COURSE = _FakeCourse("How to play chess", "Games", "Learning Chess Fundamentals")
AI_COURSE = _FakeCourse(
    "Understand the history of AI", "Artificial Intelligence", "History of AI and ML"
)


def test_chess_board_rejected_on_a_non_board_game_course():
    """The exact spec found cached against a lesson on the perceptron."""
    spec = {
        **BOARD,
        "id": "perceptron-architecture",
        "title": "Perceptron Architecture",
        "caption": "The perceptron's architecture consists of input, weighted sum and output.",
        "highlight": ["e6", "f5"],
    }
    with pytest.raises(ValueError, match="not about a board game"):
        validate_diagrams({"diagrams": [spec]}, course=AI_COURSE)


def test_the_same_board_is_fine_on_a_chess_course():
    assert len(validate_diagrams({"diagrams": [BOARD]}, course=CHESS_COURSE)) == 1


def test_a_non_chess_board_is_allowed_on_any_course():
    """A coordinate grid or matrix must stay available to every subject."""
    spec = {
        **BOARD,
        "size": 4,
        "pieces": [{"at": "b2", "glyph": "x", "tone": "brand"}],
        "highlight": ["c3", "d4"],
    }
    assert len(validate_diagrams({"diagrams": [spec]}, course=AI_COURSE)) == 1


def test_pawns_count_as_chess_pieces_for_relevance():
    """A pawn has no checkable movement but is unmistakably a chess piece."""
    spec = {**BOARD, "pieces": [{"at": "e2", "glyph": "P"}], "highlight": []}
    with pytest.raises(ValueError, match="not about a board game"):
        validate_diagrams({"diagrams": [spec]}, course=AI_COURSE)


def test_unicode_pieces_count_too():
    spec = {**BOARD, "pieces": [{"at": "d4", "glyph": "♞"}], "highlight": ["e6"]}
    with pytest.raises(ValueError, match="not about a board game"):
        validate_diagrams({"diagrams": [spec]}, course=AI_COURSE)


def test_without_a_course_the_relevance_gate_stays_open():
    """Structural validation must remain usable on its own."""
    assert len(validate_diagrams({"diagrams": [BOARD]})) == 1


def test_graph_and_plot_are_never_gated_by_course():
    assert len(validate_diagrams({"diagrams": [GRAPH]}, course=AI_COURSE)) == 1
    assert len(validate_diagrams({"diagrams": [PLOT]}, course=CHESS_COURSE)) == 1


def test_edge_to_unknown_node_rejected():
    """The single most likely model error, and invisible once drawn."""
    spec = {**GRAPH, "edges": [{"from": "open", "to": "write"}]}
    with pytest.raises(ValueError, match="unknown node 'write'"):
        validate_diagrams({"diagrams": [spec]})


def test_duplicate_node_id_rejected():
    spec = {**GRAPH, "nodes": [
        {"id": "open", "label": "open"},
        {"id": "open", "label": "open again"},
    ], "edges": []}
    with pytest.raises(ValueError, match="duplicate node id"):
        validate_diagrams({"diagrams": [spec]})


# A layout is a presentation choice, not a claim about the world. When it does
# not fit the data the data wins and the layout is downgraded to `layered`,
# which draws branching and cyclic graphs correctly. Rejecting instead would
# throw away sound nodes and edges over a stylistic mismatch.

def test_tree_layout_with_two_parents_falls_back_to_layered():
    spec = {**TREE, "edges": [
        {"from": "n8", "to": "n3"},
        {"from": "n10", "to": "n3"},
    ]}
    out = validate_diagrams({"diagrams": [spec]})
    assert out[0]["layout"] == "layered"
    assert len(out[0]["edges"]) == 2


def test_tree_layout_with_a_cycle_falls_back_to_layered():
    spec = {**TREE, "nodes": [
        {"id": "a", "label": "a"}, {"id": "b", "label": "b"}, {"id": "c", "label": "c"},
    ], "edges": [
        {"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a"},
    ]}
    assert validate_diagrams({"diagrams": [spec]})[0]["layout"] == "layered"


def test_chain_layout_that_branches_falls_back_to_layered():
    """Seen live: the model asked for a chain, then described a branch."""
    spec = {**GRAPH, "edges": [
        {"from": "open", "to": "read"},
        {"from": "open", "to": "close"},
    ]}
    assert validate_diagrams({"diagrams": [spec]})[0]["layout"] == "layered"


def test_a_real_tree_keeps_its_tree_layout():
    assert validate_diagrams({"diagrams": [TREE]})[0]["layout"] == "tree"


def test_a_real_chain_keeps_its_chain_layout():
    assert validate_diagrams({"diagrams": [GRAPH]})[0]["layout"] == "chain"


def test_an_over_long_label_is_clipped_not_rejected():
    """Length is a display concern; the renderer truncates far below this."""
    spec = {**GRAPH, "nodes": [
        {"id": "open", "label": "Proposal by John McCarthy, " * 6},
        {"id": "read", "label": "read()"},
        {"id": "close", "label": "close()"},
    ]}
    out = validate_diagrams({"diagrams": [spec]})
    assert len(out[0]["nodes"][0]["label"]) == 80
    assert out[0]["nodes"][0]["label"].endswith("…")


def test_self_loop_rejected():
    spec = {**GRAPH, "layout": "layered",
            "edges": [{"from": "open", "to": "open"}]}
    with pytest.raises(ValueError, match="self-loop"):
        validate_diagrams({"diagrams": [spec]})


def test_impossible_triangle_rejected():
    """3, 4 and 20 cannot close. Drawn naively it comes out as a wrong shape."""
    with pytest.raises(ValueError, match="triangle inequality"):
        validate_diagrams({"diagrams": [{**GEOMETRY, "sides": [3, 4, 20]}]})


def test_degenerate_triangle_rejected():
    """a + b == c collapses to a straight line."""
    with pytest.raises(ValueError, match="triangle inequality"):
        validate_diagrams({"diagrams": [{**GEOMETRY, "sides": [3, 4, 7]}]})


def test_triangle_gets_default_vertex_names():
    out = validate_diagrams({"diagrams": [GEOMETRY]})
    assert out[0]["vertices"] == ["A", "B", "C"]


def test_circle_needs_a_positive_radius():
    with pytest.raises(ValueError, match="positive radius"):
        validate_diagrams({"diagrams": [
            {**GEOMETRY, "shape": "circle", "sides": [], "radius": 0}
        ]})


def test_inverted_axis_range_rejected():
    with pytest.raises(ValueError, match="empty or inverted"):
        validate_diagrams({"diagrams": [{**PLOT, "x_range": [6, -6]}]})


def test_function_series_without_fn_rejected():
    spec = {**PLOT, "series": [{"id": "s1", "label": "x", "type": "function"}]}
    with pytest.raises(ValueError, match="needs fn"):
        validate_diagrams({"diagrams": [spec]})


def test_points_series_without_points_rejected():
    spec = {**PLOT, "series": [{"id": "s1", "label": "x", "type": "points"}]}
    with pytest.raises(ValueError, match="needs points"):
        validate_diagrams({"diagrams": [spec]})


# Excess and duplication are form, not truth, so they are repaired rather than
# used as a reason to throw away sound diagrams.

def test_a_repeated_id_drops_the_later_diagram():
    out = validate_diagrams({"diagrams": [BOARD, {**GRAPH, "id": BOARD["id"]}]})
    assert [d["kind"] for d in out] == ["board"]


def test_more_than_two_diagrams_is_capped_not_rejected():
    specs = [BOARD, {**GRAPH, "id": "g2"}, {**PLOT, "id": "p3"}]
    out = validate_diagrams({"diagrams": specs})
    assert [d["id"] for d in out] == ["knight-move", "g2"]


def test_one_bad_diagram_does_not_discard_a_good_one():
    """Seen live: a sound graph was thrown away because a board beside it was
    off-board. The graph makes no false claim, so it survives."""
    bad = {**BOARD, "id": "bad", "size": 4, "highlight": ["e4"]}
    out = validate_diagrams({"diagrams": [GRAPH, bad]})
    assert [d["kind"] for d in out] == ["graph"]


def test_a_set_where_everything_fails_still_raises():
    """Nothing usable is a real failure, and must burn a retry."""
    bad = {**BOARD, "id": "bad", "size": 4, "highlight": ["e4"]}
    with pytest.raises(ValueError, match="off a 4x4 board"):
        validate_diagrams({"diagrams": [bad]})


def test_a_non_list_diagrams_value_is_rejected():
    with pytest.raises(ValueError, match="must be a list"):
        validate_diagrams({"diagrams": "a chessboard"})


# ---------------------------------------------------------------------------
# Steps — the check that stops animation silently doing nothing
# ---------------------------------------------------------------------------

def test_steps_referencing_known_elements_accepted():
    spec = {**BOARD, "steps": [
        {"label": "Start on d4.", "highlight": ["d4"]},
        {"label": "Two up, one across.", "highlight": ["e6", "c6"]},
    ]}
    out = validate_diagrams({"diagrams": [spec]})
    assert len(out[0]["steps"]) == 2


def test_step_referencing_unknown_element_rejected():
    """Otherwise the step plays and highlights nothing at all."""
    spec = {**BOARD, "steps": [
        {"label": "Start.", "highlight": ["d4"]},
        {"label": "Jump.", "highlight": ["z9"]},
    ]}
    with pytest.raises(ValueError, match="unknown element 'z9'"):
        validate_diagrams({"diagrams": [spec]})


def test_step_referencing_unknown_graph_node_rejected():
    spec = {**GRAPH, "steps": [
        {"label": "Open it.", "highlight": ["open"]},
        {"label": "Write it.", "highlight": ["write"]},
    ]}
    with pytest.raises(ValueError, match="unknown element 'write'"):
        validate_diagrams({"diagrams": [spec]})


def test_graph_step_may_reference_an_edge():
    spec = {**GRAPH, "steps": [
        {"label": "Open the file.", "highlight": ["open"]},
        {"label": "Hand the handle on.", "highlight": ["open->read"]},
    ]}
    assert len(validate_diagrams({"diagrams": [spec]})) == 1


def test_single_step_rejected():
    """A one-frame animation is a static diagram wearing a play button."""
    spec = {**BOARD, "steps": [{"label": "Start.", "highlight": ["d4"]}]}
    with pytest.raises(ValueError, match="at least 2"):
        validate_diagrams({"diagrams": [spec]})


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def test_build_prompt_formats_without_error(db_session):
    """Guards the {{/}} escaping — an unescaped brace fails at import time."""
    lesson = _seed_lesson(db_session)
    prompt = _build_prompt(lesson)
    assert "Reading files" in prompt
    assert "Learn Python file handling" in prompt
    # The enriched body must actually reach the model, or it invents a subject.
    assert "open()" in prompt


def test_build_prompt_survives_an_unenriched_lesson(db_session):
    lesson = _seed_lesson(db_session, content_json=None)
    assert "no structured content" in _build_prompt(lesson)


def test_generate_retries_then_succeeds(db_session):
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, side_effect=["not json at all", _wrap(GRAPH)]) as mock:
        diagrams = generate_diagrams(lesson)
    assert mock.call_count == 2
    assert diagrams[0]["id"] == "file-io"


def test_generate_retries_on_an_invalid_spec(db_session):
    """A schema-valid but undrawable spec must burn a retry, not be stored."""
    lesson = _seed_lesson(db_session)
    bad = _wrap({**GRAPH, "edges": [{"from": "open", "to": "write"}]})
    with patch(DIAGRAM_PATCH, side_effect=[bad, _wrap(GRAPH)]) as mock:
        diagrams = generate_diagrams(lesson)
    assert mock.call_count == 2
    assert diagrams[0]["nodes"][0]["id"] == "open"


def test_generation_passes_the_course_into_validation(db_session):
    """A board is rejected for a Python course and accepted for a chess one.

    The same spec, the same code path — only the course differs. Without the
    course being threaded through, both would pass.
    """
    python_lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, return_value=_wrap(BOARD)):
        with pytest.raises(RuntimeError, match="after 2 attempts"):
            generate_diagrams(python_lesson)

    chess_lesson = _seed_lesson(db_session, chess=True)
    with patch(DIAGRAM_PATCH, return_value=_wrap(BOARD)):
        diagrams = generate_diagrams(chess_lesson)
    assert diagrams[0]["kind"] == "board"


def test_generate_gives_up_after_two_attempts(db_session):
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, return_value="still not json"):
        with pytest.raises(RuntimeError, match="after 2 attempts"):
            generate_diagrams(lesson)


def test_transport_error_is_not_retried(db_session):
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, side_effect=httpx.ConnectError("refused")) as mock:
        with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
            generate_diagrams(lesson)
    assert mock.call_count == 1


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

def test_endpoint_generates_and_caches(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, return_value=_wrap(GRAPH)) as mock:
        first = client.post(f"/lessons/{lesson.id}/diagram")
        second = client.post(f"/lessons/{lesson.id}/diagram")

    assert first.status_code == 200
    assert first.json()["status"] == "generated"
    assert second.json()["status"] == "cached"
    assert second.json()["diagrams"][0]["id"] == "file-io"
    assert mock.call_count == 1


def test_declining_is_cached_so_it_is_not_asked_again(client, db_session):
    """The distinction NULL vs '[]' is what stops a forever-retry every open."""
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, return_value=_wrap()) as mock:
        first = client.post(f"/lessons/{lesson.id}/diagram")
        second = client.post(f"/lessons/{lesson.id}/diagram")

    assert first.json() == {"status": "generated", "diagrams": []}
    assert second.json()["status"] == "cached"
    assert mock.call_count == 1

    db_session.expire_all()
    assert db_session.get(Lesson, lesson.id).diagram_json == "[]"


def test_failure_leaves_the_column_null_so_the_next_open_retries(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(DIAGRAM_PATCH, return_value="garbage"):
        res = client.post(f"/lessons/{lesson.id}/diagram")

    assert res.status_code == 503
    db_session.expire_all()
    assert db_session.get(Lesson, lesson.id).diagram_json is None


def test_unenriched_lesson_is_409_not_a_bad_diagram(client, db_session):
    lesson = _seed_lesson(db_session, content_json=None)
    with patch(DIAGRAM_PATCH) as mock:
        res = client.post(f"/lessons/{lesson.id}/diagram")
    assert res.status_code == 409
    assert "content generated" in res.json()["detail"]
    mock.assert_not_called()


def test_unknown_lesson_is_404(client):
    assert client.post("/lessons/does-not-exist/diagram").status_code == 404


def test_lesson_detail_exposes_diagrams(client, db_session):
    lesson = _seed_lesson(db_session)
    course_id = lesson.module.course_id
    with patch(DIAGRAM_PATCH, return_value=_wrap(GRAPH)):
        client.post(f"/lessons/{lesson.id}/diagram")

    detail = client.get(f"/courses/{course_id}/lessons/{lesson.id}").json()
    assert detail["diagrams"][0]["kind"] == "graph"


def test_detail_diagrams_is_null_before_generation(client, db_session):
    lesson = _seed_lesson(db_session)
    detail = client.get(f"/courses/{lesson.module.course_id}/lessons/{lesson.id}").json()
    assert detail["diagrams"] is None


def test_concurrent_requests_generate_once(client, db_session):
    """Two opens in flight must not both pay for a generation."""
    lesson = _seed_lesson(db_session)

    def slow(_prompt):
        import time
        time.sleep(0.15)
        return _wrap(GRAPH)

    with patch(DIAGRAM_PATCH, side_effect=slow) as mock:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(client.post, f"/lessons/{lesson.id}/diagram")
                for _ in range(2)
            ]
            results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    assert mock.call_count == 1


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

def test_narration_reads_the_caption_and_never_the_spec(db_session):
    from app.routes.audio import _build_narration_text

    lesson = _seed_lesson(db_session)
    lesson.diagram_json = json.dumps([BOARD])
    db_session.commit()

    text = _build_narration_text(lesson)
    assert "From d4 a knight reaches eight squares." in text
    for leaked in ("highlight", "e6", "kind", "board"):
        assert leaked not in text


def test_narration_unaffected_when_there_are_no_diagrams(db_session):
    from app.routes.audio import _build_narration_text

    lesson = _seed_lesson(db_session)
    before = _build_narration_text(lesson)
    lesson.diagram_json = "[]"
    db_session.commit()
    assert _build_narration_text(lesson) == before
