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

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
        return self


# ── graph ────────────────────────────────────────────────────────────────────


class GraphNode(BaseModel):
    id: str = Field(..., min_length=1, max_length=48)
    label: str = Field(..., min_length=1, max_length=80)
    tone: Tone = "neutral"


class GraphEdge(BaseModel):
    # `from` is a Python keyword, but it is by far the most natural word for a
    # model to emit. Aliased rather than renamed; every dump uses by_alias=True.
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(..., alias="from")
    to: str
    label: str | None = Field(None, max_length=80)
    directed: bool = True


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

        if self.layout == "tree":
            self._check_tree(known)
        elif self.layout == "chain":
            self._check_chain(known)
        return self

    def _check_tree(self, known: set[str]) -> None:
        """A tree layout that is not a tree lays out on top of itself."""
        parents: dict[str, str] = {}
        for edge in self.edges:
            if edge.to in parents:
                raise ValueError(
                    f"tree layout: {edge.to!r} has more than one parent"
                )
            parents[edge.to] = edge.from_

        roots = known - set(parents)
        if len(roots) != 1:
            raise ValueError(
                f"tree layout needs exactly one root, found {len(roots)}"
            )
        if len(self.edges) != len(known) - 1:
            raise ValueError(
                f"tree layout: {len(known)} nodes need {len(known) - 1} edges, "
                f"got {len(self.edges)}"
            )

        # Every node must reach the root, or there is a cycle hiding in a
        # component that the parent-count check alone cannot see.
        for start in known:
            seen: set[str] = set()
            node = start
            while node in parents:
                if node in seen:
                    raise ValueError("tree layout contains a cycle")
                seen.add(node)
                node = parents[node]

    def _check_chain(self, known: set[str]) -> None:
        """A chain is a single path: one start, one end, no branching."""
        outgoing: dict[str, int] = {}
        incoming: dict[str, int] = {}
        for edge in self.edges:
            outgoing[edge.from_] = outgoing.get(edge.from_, 0) + 1
            incoming[edge.to] = incoming.get(edge.to, 0) + 1

        if any(count > 1 for count in outgoing.values()):
            raise ValueError("chain layout: a node branches to more than one node")
        if any(count > 1 for count in incoming.values()):
            raise ValueError("chain layout: a node is reached from more than one node")
        if self.edges and len(self.edges) != len(known) - 1:
            raise ValueError("chain layout: edges do not form a single path")


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
