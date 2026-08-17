"""The diagram specification: what the model is allowed to say, and what it means.

A diagram is generated as a *semantic* spec, never as SVG markup. The model
names a kind and fills meaning-level fields — "a knight on d4, these eight
squares highlighted" — and the frontend computes every coordinate from that.

The split is deliberate. Asking an 8B model for `{"at": "d4"}` is a request it
can satisfy; asking it to place 64 `<rect>` elements by hand is one it fails at
subtly, because a single wrong coordinate still parses and still renders. It
also means colours come from theme tokens rather than hexes the model invented,
and that a spec has *invariants* — every edge endpoint exists, every highlighted
square is on the board, a triangle's sides can actually close. Markup has none.

This module is where those invariants live. A spec that fails any of them is
rejected before it is stored, which costs a retry and, at worst, means the
lesson simply has no diagram. Failing safe is the whole design: a missing
diagram is invisible, a nonsense diagram is worse than nothing.
"""

import math
import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Caps exist to bound both the render and the prompt. A 40-node graph is not a
# teaching aid, and an unbounded list is a way for one bad generation to make a
# lesson page unusable.
MAX_DIAGRAMS_PER_LESSON = 2
MAX_NODES = 24
MAX_EDGES = 40
MAX_SERIES = 4
MAX_POINTS = 60
MAX_STEPS = 6
MIN_BOARD_SIZE = 4
MAX_BOARD_SIZE = 8
MIN_POLYGON_VERTICES = 3
MAX_POLYGON_VERTICES = 8

Tone = Literal["brand", "success", "warn", "danger", "info", "neutral"]

_SQUARE_RE = re.compile(r"^([a-h])([1-8])$")


def parse_square(square: str, size: int) -> tuple[int, int] | None:
    """Algebraic square -> zero-based (file, rank), or None if off this board."""
    match = _SQUARE_RE.match(square)
    if match is None:
        return None
    file_index = ord(match.group(1)) - ord("a")
    rank_index = int(match.group(2)) - 1
    if file_index >= size or rank_index >= size:
        return None
    return file_index, rank_index


def board_squares(size: int) -> set[str]:
    """Every addressable square on a size x size board."""
    return {
        f"{chr(ord('a') + f)}{r + 1}"
        for f in range(size)
        for r in range(size)
    }


class DiagramStep(BaseModel):
    """One frame of a staged reveal."""

    label: str = Field(..., min_length=1, max_length=200)
    show: list[str] = Field(default_factory=list)
    highlight: list[str] = Field(default_factory=list)


class _DiagramBase(BaseModel):
    """Fields and checks shared by every kind.

    Unknown keys are ignored rather than rejected: a small model routinely adds
    a stray "description" or "notes", and throwing away an otherwise-correct
    diagram over that would trade a real diagram for no diagram.
    """

    id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=120)
    caption: str = Field(..., min_length=1, max_length=400)
    steps: list[DiagramStep] = Field(default_factory=list, max_length=MAX_STEPS)

    def element_ids(self) -> set[str]:
        """Every id a step may reference. Must never raise."""
        raise NotImplementedError

    @model_validator(mode="after")
    def _check_steps(self) -> "_DiagramBase":
        if not self.steps:
            return self
        # A single-frame animation is a static diagram wearing a play button.
        if len(self.steps) < 2:
            raise ValueError("steps must have at least 2 entries, or be omitted")

        known = self.element_ids()
        for position, step in enumerate(self.steps, start=1):
            for ref in (*step.show, *step.highlight):
                if ref not in known:
                    raise ValueError(
                        f"step {position} references unknown element {ref!r}"
                    )
        return self


# ── board ────────────────────────────────────────────────────────────────────

# Piece movement, as offsets. `slide` means repeat the offset to the edge.
#
# This is here because of a defect found by running generation against the live
# Chess Fundamentals course: the model produced a bishop on e2 highlighting
# a1, h8, a8, h1, c4 and f5, of which only c4 is on a diagonal. Every one of
# those is a legal square, so nothing structural could reject it — it was a
# drawable, plausible, and completely false picture of how a bishop moves.
#
# Which square a piece can reach is geometry, and geometry is the half of this
# design that belongs to code. Leaving it to the model was the mistake.
_MOVES: dict[str, tuple[list[tuple[int, int]], bool]] = {
    "N": ([(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)], False),
    "B": ([(1, 1), (1, -1), (-1, 1), (-1, -1)], True),
    "R": ([(1, 0), (-1, 0), (0, 1), (0, -1)], True),
    "Q": ([(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)], True),
    "K": ([(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)], False),
}

# Unicode pieces normalise onto the same letters; a pawn is deliberately absent,
# because its move depends on colour and history and cannot be checked here.
_GLYPH_ALIASES = {
    "♘": "N", "♞": "N", "♗": "B", "♝": "B", "♖": "R", "♜": "R",
    "♕": "Q", "♛": "Q", "♔": "K", "♚": "K",
}


def reachable_squares(glyph: str, at: str, size: int) -> set[str] | None:
    """Squares this piece could move to on an empty board.

    None means "not a piece whose movement is defined here" — an unknown glyph,
    or a pawn — in which case the caller must not check anything.
    """
    letter = _GLYPH_ALIASES.get(glyph, glyph.upper())
    move = _MOVES.get(letter)
    origin = parse_square(at, size)
    if move is None or origin is None:
        return None

    offsets, slide = move
    file_index, rank_index = origin
    out: set[str] = set()
    for df, dr in offsets:
        f, r = file_index + df, rank_index + dr
        while 0 <= f < size and 0 <= r < size:
            out.add(f"{chr(ord('a') + f)}{r + 1}")
            if not slide:
                break
            f += df
            r += dr
    return out


class BoardPiece(BaseModel):
    at: str
    glyph: str = Field(..., min_length=1, max_length=2)
    tone: Tone = "neutral"


class BoardDiagram(_DiagramBase):
    """A chessboard, coordinate grid or matrix."""

    kind: Literal["board"]
    size: int = Field(8, ge=MIN_BOARD_SIZE, le=MAX_BOARD_SIZE)
    pieces: list[BoardPiece] = Field(default_factory=list)
    highlight: list[str] = Field(default_factory=list)
    labels: bool = True

    def element_ids(self) -> set[str]:
        return board_squares(self.size)

    @model_validator(mode="after")
    def _check_squares(self) -> "BoardDiagram":
        occupied: set[str] = set()
        for piece in self.pieces:
            if parse_square(piece.at, self.size) is None:
                raise ValueError(
                    f"piece on {piece.at!r} is off a {self.size}x{self.size} board"
                )
            if piece.at in occupied:
                raise ValueError(f"two pieces on {piece.at!r}")
            occupied.add(piece.at)

        for square in self.highlight:
            if parse_square(square, self.size) is None:
                raise ValueError(
                    f"highlighted square {square!r} is off a "
                    f"{self.size}x{self.size} board"
                )

        self._check_reachability(occupied)
        return self

    def _check_reachability(self, occupied: set[str]) -> None:
        """If every piece is one whose movement is defined, highlights must fit.

        Applied only when all pieces are known chess pieces, so a board used as
        a coordinate grid or a matrix — glyphs like "1" or "x" — is unaffected.
        Highlights may be a subset (illustrating two of a knight's eight moves
        is fine); what is rejected is a square no piece present could reach.

        A false rejection costs the lesson its diagram. A false acceptance
        teaches a rule that is wrong. Given that asymmetry, this errs strict.
        """
        if not self.pieces or not self.highlight:
            return

        allowed: set[str] = set()
        for piece in self.pieces:
            squares = reachable_squares(piece.glyph, piece.at, self.size)
            if squares is None:
                return  # Not a chess board, or a pawn — nothing to check.
            allowed |= squares

        # A piece's own square is a legitimate thing to highlight.
        allowed |= occupied

        unreachable = [s for s in self.highlight if s not in allowed]
        if unreachable:
            glyphs = ", ".join(f"{p.glyph} on {p.at}" for p in self.pieces)
            raise ValueError(
                f"highlighted {unreachable} unreachable by {glyphs} — "
                "the squares do not match how the piece moves"
            )


# ── graph ────────────────────────────────────────────────────────────────────


def _clip(value: Any, limit: int) -> Any:
    """Truncate an over-long label instead of rejecting the diagram for it.

    Label length is a display concern, not a truth claim — and the renderers
    truncate to well under this anyway. Rejecting a whole diagram over one
    verbose node costs a lesson its picture and buys no correctness, which is
    the wrong side of the trade this validator exists to make. Found on the
    live History of AI course, where a 95-character node label threw away an
    otherwise sound graph.
    """
    if isinstance(value, str) and len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value


class GraphNode(BaseModel):
    id: str = Field(..., min_length=1, max_length=48)
    label: str = Field(..., min_length=1, max_length=80)
    tone: Tone = "neutral"

    @field_validator("label", mode="before")
    @classmethod
    def _clip_label(cls, value: Any) -> Any:
        return _clip(value, 80)


class GraphEdge(BaseModel):
    # `from` is a Python keyword, but it is by far the most natural word for a
    # model to emit. Aliased rather than renamed; every dump uses by_alias=True.
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    to: str
    label: str | None = Field(None, max_length=80)
    directed: bool = True

    @field_validator("label", mode="before")
    @classmethod
    def _clip_label(cls, value: Any) -> Any:
        return _clip(value, 80)


class GraphDiagram(_DiagramBase):
    """Nodes and edges: pipelines, binary trees, graphs, state machines.

    One data shape with four layouts rather than four kinds — the node/edge
    payload is identical in each case, and only the geometry differs. That also
    leaves the model one fewer thing to get wrong.
    """

    kind: Literal["graph"]
    layout: Literal["chain", "tree", "layered", "circular"] = "layered"
    nodes: list[GraphNode] = Field(..., min_length=1, max_length=MAX_NODES)
    edges: list[GraphEdge] = Field(default_factory=list, max_length=MAX_EDGES)

    def element_ids(self) -> set[str]:
        ids = {node.id for node in self.nodes}
        return ids | {f"{edge.from_}->{edge.to}" for edge in self.edges}

    @model_validator(mode="after")
    def _check_graph(self) -> "GraphDiagram":
        ids = [node.id for node in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate node id")

        known = set(ids)
        for edge in self.edges:
            if edge.from_ not in known:
                raise ValueError(f"edge from unknown node {edge.from_!r}")
            if edge.to not in known:
                raise ValueError(f"edge to unknown node {edge.to!r}")
            if edge.from_ == edge.to:
                raise ValueError(f"self-loop on {edge.from_!r}")

        # A layout is a presentation choice, not a claim about the world, so a
        # mismatch is repaired rather than rejected. The nodes and edges are the
        # content and they have already been checked; `layered` draws branching
        # and cyclic data correctly, so downgrading to it yields a correct
        # picture where rejecting would have yielded no picture at all. Seen on
        # the live History of AI course, which asked for `chain` and then
        # described a branching structure.
        if self.layout == "tree" and not self._is_tree(known):
            self.layout = "layered"
        elif self.layout == "chain" and not self._is_chain(known):
            self.layout = "layered"
        return self

    def _is_tree(self, known: set[str]) -> bool:
        """One root, one parent each, no cycle — otherwise nodes overlap."""
        parents: dict[str, str] = {}
        for edge in self.edges:
            if edge.to in parents:
                return False
            parents[edge.to] = edge.from_

        if len(known - set(parents)) != 1:
            return False
        if len(self.edges) != len(known) - 1:
            return False

        # A cycle can hide in a component the parent-count check cannot see.
        for start in known:
            seen: set[str] = set()
            node = start
            while node in parents:
                if node in seen:
                    return False
                seen.add(node)
                node = parents[node]
        return True

    def _is_chain(self, known: set[str]) -> bool:
        """A chain is a single path: no branching, no merging."""
        outgoing: dict[str, int] = {}
        incoming: dict[str, int] = {}
        for edge in self.edges:
            outgoing[edge.from_] = outgoing.get(edge.from_, 0) + 1
            incoming[edge.to] = incoming.get(edge.to, 0) + 1

        if any(count > 1 for count in outgoing.values()):
            return False
        if any(count > 1 for count in incoming.values()):
            return False
        return not self.edges or len(self.edges) == len(known) - 1


# ── plot ─────────────────────────────────────────────────────────────────────

FunctionFamily = Literal[
    "linear", "quadratic", "exponential", "sigmoid", "sine", "normal"
]


class PlotFunction(BaseModel):
    """A named curve family with numeric parameters.

    Deliberately NOT an expression string. A formula the model writes and the
    client evaluates is an execution path from model output to the runtime, and
    there is no version of that worth the convenience.
    """

    family: FunctionFamily
    params: dict[str, float] = Field(default_factory=dict)


class PlotSeries(BaseModel):
    id: str = Field(..., min_length=1, max_length=48)
    label: str = Field(..., min_length=1, max_length=80)
    tone: Tone = "brand"
    type: Literal["function", "points", "bars"]
    fn: PlotFunction | None = None
    points: list[tuple[float, float]] | None = Field(None, max_length=MAX_POINTS)

    @model_validator(mode="after")
    def _check_payload(self) -> "PlotSeries":
        if self.type == "function":
            if self.fn is None:
                raise ValueError(f"series {self.id!r}: type 'function' needs fn")
        elif not self.points:
            raise ValueError(f"series {self.id!r}: type {self.type!r} needs points")

        for point in self.points or []:
            if not all(math.isfinite(value) for value in point):
                raise ValueError(f"series {self.id!r}: non-finite point {point}")
        return self


class PlotMarker(BaseModel):
    id: str = Field(..., min_length=1, max_length=48)
    at: tuple[float, float]
    label: str = Field(..., min_length=1, max_length=80)


class PlotDiagram(_DiagramBase):
    """Curves, scatter and bars on labelled axes."""

    kind: Literal["plot"]
    x_label: str = Field(..., min_length=1, max_length=60)
    y_label: str = Field(..., min_length=1, max_length=60)
    x_range: tuple[float, float]
    y_range: tuple[float, float] | None = None
    series: list[PlotSeries] = Field(..., min_length=1, max_length=MAX_SERIES)
    markers: list[PlotMarker] = Field(default_factory=list)

    def element_ids(self) -> set[str]:
        return {s.id for s in self.series} | {m.id for m in self.markers}

    @model_validator(mode="after")
    def _check_plot(self) -> "PlotDiagram":
        for name, span in (("x_range", self.x_range), ("y_range", self.y_range)):
            if span is None:
                continue
            low, high = span
            if not (math.isfinite(low) and math.isfinite(high)):
                raise ValueError(f"{name} is not finite")
            if low >= high:
                raise ValueError(f"{name} is empty or inverted: {span}")

        ids = [s.id for s in self.series] + [m.id for m in self.markers]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate series or marker id")
        return self


# ── geometry ─────────────────────────────────────────────────────────────────


class GeometryAnnotation(BaseModel):
    at: str = Field(..., min_length=1, max_length=16)
    text: str = Field(..., min_length=1, max_length=80)


class GeometryDiagram(_DiagramBase):
    """Shapes positioned from side lengths, never from coordinates.

    A triangle is `sides: [3, 4, 5]` and the renderer derives the vertices by
    the law of cosines. That keeps the model out of the geometry business, and
    turns "can this shape exist" into a validator check rather than a drawing
    that silently comes out wrong.
    """

    kind: Literal["geometry"]
    shape: Literal["triangle", "rectangle", "polygon", "circle"]
    vertices: list[str] = Field(default_factory=list, max_length=MAX_POLYGON_VERTICES)
    sides: list[float] = Field(default_factory=list, max_length=MAX_POLYGON_VERTICES)
    radius: float | None = None
    show_sides: bool = True
    show_angles: bool = False
    annotations: list[GeometryAnnotation] = Field(default_factory=list)

    def element_ids(self) -> set[str]:
        ids: set[str] = {"shape"}
        ids |= set(self.vertices)
        ids |= {f"angle:{v}" for v in self.vertices}
        count = len(self.vertices)
        for i in range(count):
            ids.add(f"{self.vertices[i]}{self.vertices[(i + 1) % count]}")
        return ids

    @model_validator(mode="after")
    def _check_shape(self) -> "GeometryDiagram":
        if self.shape == "circle":
            if self.radius is None or self.radius <= 0:
                raise ValueError("circle needs a positive radius")
            return self

        if any(length <= 0 for length in self.sides):
            raise ValueError("side lengths must be positive")

        if self.shape == "triangle":
            if len(self.sides) != 3:
                raise ValueError(f"triangle needs 3 sides, got {len(self.sides)}")
            a, b, c = sorted(self.sides)
            # Degenerate triangles (a + b == c) collapse to a line.
            if a + b <= c:
                raise ValueError(
                    f"sides {self.sides} violate the triangle inequality"
                )
            self._default_vertices(3)
        elif self.shape == "rectangle":
            if len(self.sides) != 2:
                raise ValueError(
                    f"rectangle needs 2 sides (width, height), got {len(self.sides)}"
                )
            self._default_vertices(4)
        else:  # polygon — regular, with one vertex per corner
            count = len(self.vertices)
            if not MIN_POLYGON_VERTICES <= count <= MAX_POLYGON_VERTICES:
                raise ValueError(
                    f"polygon needs {MIN_POLYGON_VERTICES}-{MAX_POLYGON_VERTICES} "
                    f"vertices, got {count}"
                )

        if len(set(self.vertices)) != len(self.vertices):
            raise ValueError("duplicate vertex name")
        return self

    def _default_vertices(self, count: int) -> None:
        """Name the corners A, B, C… when the model did not."""
        if not self.vertices:
            self.vertices = [chr(ord("A") + i) for i in range(count)]
        elif len(self.vertices) != count:
            raise ValueError(
                f"{self.shape} needs {count} vertices, got {len(self.vertices)}"
            )


# ── the union ────────────────────────────────────────────────────────────────

DiagramSpec = Annotated[
    Union[BoardDiagram, GraphDiagram, PlotDiagram, GeometryDiagram],
    Field(discriminator="kind"),
]


class DiagramSet(BaseModel):
    """What one generation call returns.

    An empty list is a valid, cacheable answer: most language-grammar lessons
    are not helped by a picture, and a diagram added for the sake of having one
    costs the reader attention it does not repay.
    """

    diagrams: list[DiagramSpec] = Field(
        default_factory=list, max_length=MAX_DIAGRAMS_PER_LESSON
    )

    @model_validator(mode="after")
    def _unique_ids(self) -> "DiagramSet":
        ids = [d.id for d in self.diagrams]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate diagram id")
        return self


def validate_diagrams(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a raw model response into storable diagram dicts.

    Raises ValueError (Pydantic's ValidationError subclasses it) so the caller's
    existing retry branch catches this the same way it catches a parse failure.
    """
    parsed = DiagramSet.model_validate(payload)
    return [d.model_dump(mode="json", by_alias=True) for d in parsed.diagrams]
