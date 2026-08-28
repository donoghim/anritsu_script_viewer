import math
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainterPath,
    QPainter, QWheelEvent, QFontMetrics
)

from anritsu_parser import AnritsuNode

# ── Color Palette ──────────────────────────────────────────────────────────────
COLOR_START       = QColor(225, 228, 232)
COLOR_PROCEDURE   = QColor(218, 234, 254)
COLOR_COMPOUND    = QColor(254, 218, 218)
COLOR_TERMINATOR  = QColor(218, 254, 218)
COLOR_WAIT_EVENT  = QColor(255, 240, 150)
COLOR_LOG_MESSAGE = QColor(255, 255, 255)
COLOR_CONDITIONAL_BRANCH = QColor(224, 204, 239)

BORDER_START      = QColor(130, 130, 130)
BORDER_PROCEDURE  = QColor(60, 120, 210)
BORDER_COMPOUND   = QColor(210, 60, 60)
BORDER_TERMINATOR = QColor(60, 170, 60)
BORDER_WAIT_EVENT = QColor(190, 150, 20)
BORDER_SELECTED   = QColor(30, 90, 255)

# Connector colors
COL_NORMAL   = QColor(40, 150, 40)    # green  – normal straight down
COL_EXCEP    = QColor(210, 30, 30)    # red    – Timeout / False / Fail
COL_RETURN   = QColor(20, 80, 200)    # blue   – exception→normal return path

# Labels that indicate a NORMAL flow (will route straight down or right-col straight)
NORMAL_LABELS = {"ok", "assigned", "logged", "displayed",
                 "true", "response received", "timerstarted", "timerexpired",
                 "timerstopped", "authentication response",
                 "security mode complete (emm)", "security mode complete (rrc)", ""}
# Labels that indicate an EXCEPTION/ERROR branch
EXCEPT_LABELS = {"timeout", "false", "fail", "failed", "error",
                 "system error"}


class GraphicsNodeItem(QGraphicsRectItem):
    """Single action node rendered as a rectangle with a text label."""
    NODE_WIDTH  = 270
    NODE_HEIGHT = 44

    def __init__(self, node: AnritsuNode, scope_prefix: str = "root",
                 viewer=None, parent=None):
        super().__init__(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT, parent)
        self.node = node
        self.scope_prefix = scope_prefix
        self.viewer = viewer
        self.is_selected_node = False
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self._init_style()

    def _init_style(self):
        name_lower = self.node.name.lower()
        if self.node.action_type == "START":
            self.fill_color, self.border_color = COLOR_START, BORDER_START
        elif self.node.type == "compoundAction" or self.node.child_actions:
            self.fill_color, self.border_color = COLOR_COMPOUND, BORDER_COMPOUND
        elif "terminator" in name_lower or self.node.action_type == "END":
            self.fill_color, self.border_color = COLOR_TERMINATOR, BORDER_TERMINATOR
        elif name_lower == "logmessage":
            self.fill_color, self.border_color = COLOR_LOG_MESSAGE, BORDER_PROCEDURE
        elif self.node.action_type == "CONDITIONAL_BRANCH":
            self.fill_color, self.border_color = COLOR_CONDITIONAL_BRANCH, QColor(130, 70, 170)
        elif any(k in name_lower for k in ("wait", "timer", "event", "mmi")):
            self.fill_color, self.border_color = COLOR_WAIT_EVENT, BORDER_WAIT_EVENT
        else:
            self.fill_color, self.border_color = COLOR_PROCEDURE, BORDER_PROCEDURE

        self.setBrush(QBrush(self.fill_color))
        self.setPen(QPen(self.border_color, 2))

        prefix  = f"[{'+' if self.node.child_actions else ''}] " if self.node.child_actions else ""
        step_id = f"{self.scope_prefix}:{self.node.id}" if self.scope_prefix else self.node.id
        title = f"{prefix}{step_id}: {self.node.name}"
        if self.viewer is None or self.viewer.show_detail:
            value_parts = self._timing_values()
            display_name = self._display_name_value()
            condition = self._condition_value()
            if condition:
                value_parts.insert(0, f"Condition: {condition}")
            if display_name:
                value_parts.insert(0, f"DisplayName: {display_name}")
            if value_parts:
                title += "\n" + self._truncate_detail(" | ".join(value_parts))

        self.text_item = QGraphicsTextItem(title, self)
        self.text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.text_item.setFont(QFont("Malgun Gothic", 8, QFont.Weight.Bold))
        self.text_item.setDefaultTextColor(QColor(25, 25, 25))
        tr = self.text_item.boundingRect()
        self.text_item.setPos(
            (self.NODE_WIDTH  - tr.width())  / 2,
            (self.NODE_HEIGHT - tr.height()) / 2
        )

    def _truncate_detail(self, detail: str) -> str:
        font = QFont("Malgun Gothic", 8, QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        max_width = self.NODE_WIDTH - 16
        if metrics.horizontalAdvance(detail) <= max_width:
            return detail

        ellipsis = "..."
        available_width = max_width - metrics.horizontalAdvance(ellipsis)
        visible_length = 0
        for index, character in enumerate(detail):
            if metrics.horizontalAdvance(detail[:index + 1]) > available_width:
                break
            visible_length = index + 1
        return detail[:visible_length] + ellipsis

    def _timing_values(self) -> List[str]:
        timeout_value = ""
        duration_value = ""
        for parameter in self.node.parameters:
            for element in parameter.iter():
                element_name = element.tag.split("}")[-1].lower()
                if element_name == "timeout":
                    for child in element.iter():
                        child_name = child.tag.split("}")[-1].lower()
                        if child_name in {"value-", "variable-", "valuemodify-"} and (child.text or "").strip():
                            timeout_value = (child.text or "").strip()
                            break
                elif element_name == "duration" and (element.text or "").strip():
                    duration_value = (element.text or "").strip()

        values = []
        if timeout_value:
            values.append(f"Timeout: {timeout_value}")
        if duration_value:
            values.append(f"Duration: {duration_value}")
        return values

    def _display_name_value(self) -> str:
        for parameter in self.node.parameters:
            for element in parameter.iter():
                if element.tag.split("}")[-1].lower() == "displayname":
                    return (element.text or "").strip()
        return ""

    def _condition_value(self) -> str:
        if self.node.action_type != "CONDITIONAL_BRANCH":
            return ""
        for parameter in self.node.parameters:
            for element in parameter.iter():
                if element.tag.split("}")[-1].lower() == "conditionalexpression":
                    return (element.text or "").strip()
                if element.tag.split("}")[-1].lower() == "controlvariable":
                    values = []
                    for child in element.iter():
                        if child is element:
                            continue
                        child_name = child.tag.split("}")[-1]
                        child_value = (child.text or "").strip()
                        if child_value and child_name.lower() not in {"value", "value-"}:
                            values.append(f"{child_name}={child_value}")
                    if values:
                        return ", ".join(values)
        return ""

    def set_node_selected(self, selected: bool):
        self.is_selected_node = selected
        self.setPen(QPen(BORDER_SELECTED if selected else self.border_color,
                         3 if selected else 2))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.viewer:
            self.viewer.handle_node_click(self)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if self.viewer:
            self.viewer.handle_node_double_click(self)


class CustomGraphicsView(QGraphicsView):
    """Ctrl+wheel zooms; plain wheel scrolls normally."""
    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)


class FlowchartViewer(QWidget):
    """
    Orthogonal flowchart viewer.  See REQUIREMENTS_SPEC.md for full spec.

    Connector routing summary
    ─────────────────────────
    A. Normal → Normal (same col, normal label): straight vertical ↓  (green)
    B. Normal → Exception               : L→R 3-segment bridge  →  (red)
    C. Right-col → Right-col, normal lbl: straight vertical ↓  (green)
    D. Any → Any, back/return edge      : outer bus, R→L ←  (blue)

    Bus-track uniqueness
    ─────────────────────
    B: bus_x starts at 490, steps -20 per connection  (490,470,450,430,…)
    D: bus_x starts at 820, steps +26 per connection  (820,846,872,…)
    → Each connection gets its own vertical track X → ZERO line overlap.
    """
    node_selected     = pyqtSignal(object)
    compound_selected = pyqtSignal(object)

    def __init__(self, title: str = "Flowchart View", parent=None):
        super().__init__(parent)
        self.title_str            = title
        self.current_scope_prefix = "root"
        self.node_items: Dict[str, GraphicsNodeItem] = {}
        self.selected_item: Optional[GraphicsNodeItem] = None
        self.use_display_layout = False
        self.show_detail = True
        self.show_main_stream_only = False
        self.connector_items_by_source: Dict[str, List[tuple]] = {}
        self.connector_items_by_target: Dict[str, List[tuple]] = {}
        self.highlighted_connector_items: List[tuple] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        hdr = QHBoxLayout()
        self.lbl_title = QLabel(self.title_str)
        self.lbl_title.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        hdr.addWidget(self.lbl_title)

        self.btn_center_selected = QPushButton("Center Selected")
        self.btn_center_selected.setVisible(self.title_str.startswith("Main Scope"))
        self.btn_center_selected.clicked.connect(self.center_selected_node)
        hdr.addWidget(self.btn_center_selected, alignment=Qt.AlignmentFlag.AlignRight)

        self.btn_close = QPushButton("Close Child Scope")
        self.btn_close.setVisible(False)
        hdr.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(hdr)

        self.scene = QGraphicsScene(self)
        self.view  = CustomGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        layout.addWidget(self.view)

    # ═══════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════
    def set_scope(self, nodes: List[AnritsuNode], scope_prefix: str = "root"):
        self.current_scope_prefix = scope_prefix
        self.lbl_title.setText(f"Scope: {scope_prefix}")
        self.scene.clear()
        self.node_items.clear()
        self.selected_item = None
        self.connector_items_by_source.clear()
        self.connector_items_by_target.clear()
        self.highlighted_connector_items.clear()

        if not nodes:
            return

        # Root and child scopes use the same graph-first layout so branch
        # targets stay below their sources in both views.
        self._set_child_scope(nodes, scope_prefix)
        return

    def set_use_display_layout(self, enabled: bool):
        self.use_display_layout = enabled
        return

    def set_show_detail(self, enabled: bool):
        self.show_detail = enabled
        return

    def set_show_main_stream_only(self, enabled: bool):
        self.show_main_stream_only = enabled
        return

        node_id_map: Dict[str, AnritsuNode] = {n.id: n for n in nodes}
        visited: set                          = set()
        ordered: List[AnritsuNode]            = []
        exc_set: Dict[str, bool]              = {}

        start_node = next(
            (n for n in nodes if n.action_type == "START" or n.id == "0"), nodes[0]
        )
        is_main = (scope_prefix == "root")

        # ── 1. Deterministic topological ordering ──────────────────────────────
        # DFS preorder can place a join target before another one of its sources,
        # producing a connector that travels upward through unrelated nodes.
        # Kahn's algorithm places every source before its reachable target.
        incoming_count: Dict[str, int] = {node.id: 0 for node in nodes}
        following_ids: Dict[str, List[str]] = {node.id: [] for node in nodes}
        predecessor_ids: Dict[str, List[str]] = {node.id: [] for node in nodes}
        incoming_labels: Dict[str, Dict[str, List[str]]] = {
            node.id: {} for node in nodes
        }
        primary_outcome_ids: Dict[str, Optional[str]] = {}
        for node in nodes:
            primary_target_id: Optional[str] = None
            for outcome in node.outcomes:
                target_id = outcome['followingActionId']
                if target_id in node_id_map:
                    following_ids[node.id].append(target_id)
                    predecessor_ids[target_id].append(node.id)
                    incoming_labels[target_id].setdefault(node.id, []).append(
                        outcome['name'].strip().lower()
                    )
                    incoming_count[target_id] += 1
                    if primary_target_id is None and outcome['name'].strip().lower() in NORMAL_LABELS:
                        primary_target_id = target_id
            primary_outcome_ids[node.id] = primary_target_id

        ready = [node for node in nodes if incoming_count[node.id] == 0]
        if start_node in ready:
            ready.remove(start_node)
            ready.insert(0, start_node)

        while ready:
            node = ready.pop(0)
            if node.id in visited:
                continue
            visited.add(node.id)
            ordered.append(node)
            for target_id in following_ids[node.id]:
                incoming_count[target_id] -= 1
                if incoming_count[target_id] == 0:
                    ready.append(node_id_map[target_id])

        # A cycle has no zero-incoming node. Keep such nodes visible after the
        # acyclic flow; their connectors use the existing return-lane rules.
        for node in nodes:
            if node.id not in visited:
                visited.add(node.id)
                ordered.append(node)

        # ── 1a. Identify the primary stream ───────────────────────────────────
        # The first normal outcome from the scenario start defines the main
        # vertical path. All other chains are auxiliary and use the right column.
        main_stream_ids: set = set()
        current_node = start_node
        while current_node and current_node.id not in main_stream_ids:
            main_stream_ids.add(current_node.id)
            next_node = None
            for outcome in current_node.outcomes:
                target_id = outcome['followingActionId']
                if outcome['name'].strip().lower() in NORMAL_LABELS and target_id in node_id_map:
                    next_node = node_id_map[target_id]
                    break
            current_node = next_node

        # Keep the primary stream visually continuous before placing auxiliary
        # chains. The relative order of each group remains topological.
        ordered = (
            [node for node in ordered if node.id in main_stream_ids] +
            [node for node in ordered if node.id not in main_stream_ids]
        )

        # Group auxiliary nodes by weakly connected component so independent
        # streams can be placed consecutively in one lane without overlapping
        # their downward connector segments.
        auxiliary_ids = {node.id for node in ordered if node.id not in main_stream_ids}
        component_by_id: Dict[str, int] = {}
        component_nodes: Dict[int, set] = {}
        component_id = 0
        for node in ordered:
            if node.id not in auxiliary_ids or node.id in component_by_id:
                continue
            pending = [node.id]
            members: set = set()
            while pending:
                current_id = pending.pop()
                if current_id in members:
                    continue
                members.add(current_id)
                neighbours = following_ids[current_id] + predecessor_ids[current_id]
                pending.extend(neighbour_id for neighbour_id in neighbours if neighbour_id in auxiliary_ids)
            for member_id in members:
                component_by_id[member_id] = component_id
            component_nodes[component_id] = members
            component_id += 1

        # Keep every component contiguous. Components with no shared nodes have
        # no overlapping internal vertical segments, so they can reuse lane 1.
        ordered = (
            [node for node in ordered if node.id in main_stream_ids] +
            [
                node
                for current_component in range(component_id)
                for node in ordered
                if component_by_id.get(node.id) == current_component
            ]
        )

        # A join remains in the rightmost predecessor lane. Every non-primary
        # outcome starts a separately progressing stream in the next rightward
        # lane, regardless of its result label (wait, Timeout, System Error, ...).
        stream_lane: Dict[str, int] = {}
        for node in ordered:
            if node.id in main_stream_ids:
                stream_lane[node.id] = 0
                continue
            auxiliary_predecessors = [
                stream_lane[pred_id] + (
                    0 if primary_outcome_ids.get(pred_id) == node.id else 1
                )
                for pred_id in predecessor_ids[node.id]
                if pred_id in stream_lane and pred_id not in main_stream_ids
            ]
            if auxiliary_predecessors:
                stream_lane[node.id] = max(auxiliary_predecessors)
            else:
                stream_lane[node.id] = 1

        # ── 2. Exception-column classification ─────────────────────────────────
        # Rule: a node is placed on the RIGHT (exception) column ONLY if it is
        # reached EXCLUSIVELY by exception labels (Timeout/False/Fail/Error).
        # If ANY incoming edge carries a normal label (OK/True/Logged/…),
        # the node stays on the LEFT column.
        if not is_main:
            normal_tgts: set = set()
            excep_tgts:  set = set()
            for node in ordered:
                for oc in node.outcomes:
                    lbl = oc['name'].strip().lower()
                    tid = oc['followingActionId']
                    if tid not in node_id_map:
                        continue
                    if lbl in NORMAL_LABELS:          # includes "true"
                        normal_tgts.add(tid)
                    elif lbl in EXCEPT_LABELS:
                        excep_tgts.add(tid)
            for tid in excep_tgts:
                if tid not in normal_tgts:
                    exc_set[tid] = True

        # ── 3. Layout constants ─────────────────────────────────────────────────
        W  = GraphicsNodeItem.NODE_WIDTH    # 270
        H  = GraphicsNodeItem.NODE_HEIGHT   # 44
        NX = 100    # normal (left) column X
        Y0 = 40
        DY = 55

        # Sub-heights for right-side exit points (Rule 8 — REQUIREMENTS_SPEC.md)
        H1 = H // 3         # ≈14 px  → False / Fail  (upper-right exit)
        H2 = (2 * H) // 3  # ≈29 px  → Timeout       (lower-right exit)

        # Right-side bus tracks (used by False, Timeout, Fail):
        #   Start just past the node right edge, step rightward.
        RIGHT_BUS_BASE = NX + W + 25   # = 395
        RIGHT_BUS_STEP = 30            # 395, 425, 455, 485, 515, 545 …

        # Give each stream column only enough space for its outgoing branch
        # lanes. This keeps simple flows compact while preventing bus overlap
        # before a busy column's next neighbour.
        branch_count_by_lane: Dict[int, int] = {}
        order_index = {node.id: index for index, node in enumerate(ordered)}
        for node in nodes:
            source_lane = stream_lane[node.id]
            for outcome in node.outcomes:
                target_id = outcome['followingActionId']
                if target_id not in stream_lane:
                    continue
                label = outcome['name'].strip().lower()
                is_branch = (
                    label in EXCEPT_LABELS or
                    label == "true" or
                    stream_lane[target_id] > source_lane or
                    (
                        label in NORMAL_LABELS and
                        stream_lane[target_id] == source_lane and
                        order_index[target_id] > order_index[node.id] + 1
                    )
                )
                if is_branch:
                    branch_count_by_lane[source_lane] = (
                        branch_count_by_lane.get(source_lane, 0) + 1
                    )

        lane_x: Dict[int, float] = {0: NX}
        max_lane = max(stream_lane.values(), default=0)
        for lane in range(1, max_lane + 1):
            previous_lane = lane - 1
            branch_count = branch_count_by_lane.get(previous_lane, 0)
            gap = max(55, 45 + branch_count * RIGHT_BUS_STEP)
            lane_x[lane] = lane_x[previous_lane] + W + gap

        # Return bus tracks use the actual source/destination columns.
        RETURN_BUS_STEP = 30           # 880, 910, 940 …

        # Left-side tracks for True exits:
        TRUE_TRACK_BASE = NX - 40      # = 60
        TRUE_TRACK_STEP = 20           # 60, 40, 20, 0 …  (steps further LEFT)

        right_idx_by_source: Dict[float, int] = {}
        return_idx = 0  # return bus index
        true_idx   = 0  # True left-track index
        normal_branch_idx_by_corridor: Dict[tuple, int] = {}

        # ── 4. Position nodes ───────────────────────────────────────────────────
        y = Y0
        pos_map: Dict[str, QPointF] = {}
        for node in ordered:
            x = lane_x[stream_lane[node.id]]
            pos_map[node.id] = QPointF(x, y)
            y += H + DY

        # ── 5. (Group containers removed — see REQUIREMENTS_SPEC.md v1.3.0) ────

        # ── 6. Place node graphics ──────────────────────────────────────────────
        for node in ordered:
            item = GraphicsNodeItem(node, scope_prefix, viewer=self)
            item.setPos(pos_map[node.id])
            self.scene.addItem(item)
            self.node_items[node.id] = item

        # ── 7. Draw connectors (label-based exit-point routing) ─────────────────
        #
        # RULES  (REQUIREMENTS_SPEC.md Rule 8 – v1.4.0)
        # ┌─────────────────────────────────────────────────────────────────────┐
        # │ Label        │ Exit point on source box    │ Color  │ Arrow dir     │
        # ├─────────────────────────────────────────────────────────────────────┤
        # │ OK/Logged/…  │ BOTTOM CENTER               │ green  │ ↓ into top   │
        # │ True         │ LEFT  CENTER                │ green  │ → into left  │
        # │ False/Fail   │ RIGHT UPPER  (Y + H/3)      │ red    │ → into left  │
        # │ Timeout      │ RIGHT LOWER  (Y + 2H/3)     │ red    │ → into left  │
        # └─────────────────────────────────────────────────────────────────────┘
        # Each False/Timeout uses a UNIQUE right-bus X lane (RIGHT_BUS_BASE + n*30).
        # Each True     uses a UNIQUE left-track X lane (TRUE_TRACK_BASE - n*20).
        # Each Return   uses a UNIQUE return-bus X lane (RETURN_BUS_BASE + n*30).
        # → No two connector segments ever share the same X or Y coordinate.
        #
        for node in ordered:
            src = self.node_items.get(node.id)
            if not src:
                continue

            for oc in node.outcomes:
                dst = self.node_items.get(oc['followingActionId'])
                if not dst:
                    continue

                lbl       = oc['name'].strip().lower()
                out_label = oc['name']

                # Label-specific exits take priority in every scope.  This keeps
                # condition branches readable even when their target is in the
                # same column as the source.
                if lbl == "true":
                    tx = TRUE_TRACK_BASE - true_idx * TRUE_TRACK_STEP
                    true_idx += 1
                    self._conn_true(src, dst, out_label, tx)
                    continue

                if lbl in {"false", "fail", "failed", "error", "system error"}:
                    source_x = src.pos().x()
                    track_index = right_idx_by_source.get(source_x, 0)
                    right_idx_by_source[source_x] = track_index + 1
                    bx = source_x + W + 25 + track_index * RIGHT_BUS_STEP
                    self._conn_false(src, dst, out_label, bx)
                    continue

                if lbl == "timeout":
                    source_x = src.pos().x()
                    track_index = right_idx_by_source.get(source_x, 0)
                    right_idx_by_source[source_x] = track_index + 1
                    bx = source_x + W + 25 + track_index * RIGHT_BUS_STEP
                    self._conn_timeout(src, dst, out_label, bx)
                    continue

                # A normal outcome can still be a graph back-edge when its
                # destination was placed earlier by DFS.  It must not be drawn
                # as an upward green line through intervening boxes.
                if lbl in NORMAL_LABELS and dst.pos().y() <= src.pos().y():
                    rx = max(src.pos().x(), dst.pos().x()) + W + 50 + return_idx * RETURN_BUS_STEP
                    return_idx += 1
                    self._conn_return(src, dst, out_label, rx)
                    continue

                # Normal/unknown outcomes stay vertical within one stream. A
                # transition to a later stream uses a green orthogonal branch.
                if abs(src.pos().x() - dst.pos().x()) < 10:
                    has_intervening_node = any(
                        other is not src and other is not dst and
                        abs(other.pos().x() - src.pos().x()) < 10 and
                        src.pos().y() < other.pos().y() < dst.pos().y()
                        for other in self.node_items.values()
                    )
                    if has_intervening_node:
                        corridor = (src.pos().x(), dst.pos().x())
                        track_index = normal_branch_idx_by_corridor.get(corridor, 0)
                        normal_branch_idx_by_corridor[corridor] = track_index + 1
                        bx = src.pos().x() + W + 25 + track_index * RIGHT_BUS_STEP
                        self._conn_normal_branch(src, dst, out_label, bx, track_index)
                    else:
                        self._conn_straight(src, dst, out_label)
                elif dst.pos().x() > src.pos().x():
                    corridor = (src.pos().x(), dst.pos().x())
                    track_index = normal_branch_idx_by_corridor.get(corridor, 0)
                    normal_branch_idx_by_corridor[corridor] = track_index + 1
                    bx = src.pos().x() + W + 25 + track_index * RIGHT_BUS_STEP
                    self._conn_normal_branch(src, dst, out_label, bx, track_index)
                else:
                    rx = max(src.pos().x(), dst.pos().x()) + W + 50 + return_idx * RETURN_BUS_STEP
                    return_idx += 1
                    self._conn_return(src, dst, out_label, rx)

        self.scene.setSceneRect(
            self.scene.itemsBoundingRect().adjusted(-100, -60, 420, 60)
        )

    def _set_child_scope(self, nodes: List[AnritsuNode], scope_prefix: str):
        """Lay out a child scope from a complete edge map before rendering it."""
        W = GraphicsNodeItem.NODE_WIDTH
        H = GraphicsNodeItem.NODE_HEIGHT
        node_map = {node.id: node for node in nodes}
        node_order = {node.id: index for index, node in enumerate(nodes)}
        edges: List[Dict[str, object]] = []
        outgoing: Dict[str, List[Dict[str, object]]] = {node.id: [] for node in nodes}
        incoming: Dict[str, List[Dict[str, object]]] = {node.id: [] for node in nodes}

        for source in nodes:
            for outcome_index, outcome in enumerate(source.outcomes):
                target_id = outcome['followingActionId']
                if target_id not in node_map:
                    continue
                label = outcome['name'].strip().lower()
                edge = {
                    "source": source.id,
                    "target": target_id,
                    "label": outcome['name'],
                    "normal": label in NORMAL_LABELS,
                    "index": len(edges),
                    "outcome_index": outcome_index,
                }
                edges.append(edge)
                outgoing[source.id].append(edge)
                incoming[target_id].append(edge)

        start_node = next(
            (node for node in nodes if node.action_type == "START" or node.id == "0"),
            nodes[0],
        )
        primary_node_ids: set = set()
        pending_node_ids = [start_node.id]
        while pending_node_ids:
            node_id = pending_node_ids.pop()
            if node_id in primary_node_ids:
                continue
            primary_node_ids.add(node_id)
            pending_node_ids.extend(
                edge["target"]
                for edge in outgoing[node_id]
                if edge["target"] not in primary_node_ids
            )
        if self.show_main_stream_only and len(primary_node_ids) != len(node_map):
            primary_nodes = [node for node in nodes if node.id in primary_node_ids]
            self._set_child_scope(primary_nodes, scope_prefix)
            return

        def edge_key(edge: Dict[str, object]):
            return (
                node_order[edge["source"]],
                0 if edge["normal"] else 1,
                edge["outcome_index"],
            )

        for edge_list in outgoing.values():
            edge_list.sort(key=edge_key)

        # Topological levels ensure tree edges always point to a later level.
        indegree = {node.id: len(incoming[node.id]) for node in nodes}
        ready = [node_id for node_id, degree in indegree.items() if degree == 0]
        ready.sort(key=lambda node_id: (node_id != start_node.id, node_order[node_id]))
        ordered_ids: List[str] = []
        rank: Dict[str, int] = {node_id: 0 for node_id in ready}

        while ready:
            source_id = ready.pop(0)
            ordered_ids.append(source_id)
            for edge in outgoing[source_id]:
                target_id = edge["target"]
                rank[target_id] = max(rank.get(target_id, 0), rank[source_id] + 1)
                indegree[target_id] -= 1
                if indegree[target_id] == 0:
                    ready.append(target_id)
                    ready.sort(key=lambda node_id: (rank[node_id], node_order[node_id]))

        # Cycles cannot be topologically ordered; place their remaining nodes
        # after the acyclic levels and render their links through outer lanes.
        next_rank = max(rank.values(), default=0) + 1
        for node in nodes:
            if node.id not in ordered_ids:
                ordered_ids.append(node.id)
                rank[node.id] = next_rank
                next_rank += 1

        # The main vertical spine follows a path from START to a terminator.
        # Only edges returning to nodes already on that path are excluded.
        primary_edge_indices: set = set()
        primary_node_ids: set = set()
        primary_node_order: List[str] = []

        terminator_ids = {
            node.id
            for node in nodes
            if "terminator" in node.name.lower()
            or node.action_type.endswith("TERMINATOR")
            or node.action_type == "END"
        }

        def longest_terminator_path_length(node_id: str, excluded_ids: set) -> int:
            if node_id in terminator_ids:
                return 1

            visited_ids = set(excluded_ids)
            visited_ids.add(node_id)
            next_lengths = [
                longest_terminator_path_length(edge["target"], visited_ids)
                for edge in outgoing[node_id]
                if edge["target"] not in visited_ids
            ]
            reachable_lengths = [length for length in next_lengths if length]
            return 1 + max(reachable_lengths, default=0) if reachable_lengths else 0

        def is_spine_return_edge(edge: Dict[str, object]) -> bool:
            return edge["target"] in primary_node_ids

        current_id = start_node.id
        while current_id not in primary_node_ids:
            primary_node_ids.add(current_id)
            primary_node_order.append(current_id)
            main_candidates = [
                edge for edge in outgoing[current_id]
                if not is_spine_return_edge(edge)
                and longest_terminator_path_length(edge["target"], primary_node_ids)
            ]
            primary_edge = max(
                main_candidates,
                key=lambda edge: (
                    longest_terminator_path_length(edge["target"], primary_node_ids),
                    -edge["outcome_index"],
                ),
                default=None,
            )
            if primary_edge is None:
                break
            primary_edge_indices.add(primary_edge["index"])
            current_id = primary_edge["target"]

        main_spine_node_ids = primary_node_ids
        main_spine_edge_indices = primary_edge_indices
        primary_node_ids = set()
        pending_node_ids = [start_node.id]
        while pending_node_ids:
            node_id = pending_node_ids.pop()
            if node_id in primary_node_ids:
                continue
            primary_node_ids.add(node_id)
            pending_node_ids.extend(
                edge["target"]
                for edge in outgoing[node_id]
                if edge["target"] not in primary_node_ids
            )
        start_unreachable_node_ids = set(node_map) - primary_node_ids

        # Select one deterministic parent per node. Normal outcomes win, which
        # keeps the normal path vertically continuous in the generated tree.
        tree_parent: Dict[str, str] = {}
        tree_edge_indices: set = set()
        for target_id, target_edges in incoming.items():
            candidates = [
                edge for edge in target_edges
                if rank.get(edge["source"], 0) < rank.get(target_id, 0)
            ]
            if not candidates:
                continue
            parent_edge = min(
                candidates,
                key=lambda edge: (
                    0 if edge["index"] in main_spine_edge_indices else 1,
                    edge_key(edge),
                ),
            )
            tree_parent[target_id] = parent_edge["source"]
            tree_edge_indices.add(parent_edge["index"])

        # The first pass uses complete-DAG ranks to choose valid tree parents.
        # Re-rank from that tree so a normal continuation occupies the next
        # level below its parent; non-tree exception paths must not push it down.
        tree_rank: Dict[str, int] = {}
        for node_id in ordered_ids:
            parent_id = tree_parent.get(node_id)
            tree_rank[node_id] = tree_rank.get(parent_id, -1) + 1
        rank = tree_rank
        # A selected main-flow edge has stronger placement priority than a
        # competing incoming tree edge: its successor must be the next row.
        for level, node_id in enumerate(primary_node_order):
            rank[node_id] = level

        # Keep auxiliary targets below every source that reaches them. The
        # ordered list is topological for acyclic edges, so one forward pass
        # prevents cross-column connectors from travelling upward. Main-flow
        # levels remain fixed by the rule above.
        for source_id in sorted(
            ordered_ids,
            key=lambda node_id: (rank[node_id], node_order[node_id]),
        ):
            for edge in outgoing[source_id]:
                target_id = edge["target"]
                if target_id not in main_spine_node_ids:
                    rank[target_id] = max(rank[target_id], rank[source_id] + 1)

        # A terminal node cannot introduce a cycle. Keep it below every direct
        # predecessor even when a cyclic group raised that predecessor's rank
        # after the main propagation pass.
        for node_id in ordered_ids:
            if outgoing[node_id] or not incoming[node_id]:
                continue
            rank[node_id] = max(
                rank[edge["source"]] + 1
                for edge in incoming[node_id]
            )

        # Detached entry nodes have no incoming edge, so topological sorting
        # initially places them at the top. When one joins the graph through
        # an outgoing edge, move it immediately above its nearest target to
        # shorten that connector while keeping the flow downward.
        for node_id in ordered_ids:
            if node_id == start_node.id or incoming[node_id] or not outgoing[node_id]:
                continue
            nearest_target_level = min(
                rank[edge["target"]]
                for edge in outgoing[node_id]
            )
            rank[node_id] = max(0, nearest_target_level - 1)

        # Each auxiliary flow continues through its first defined outcome,
        # regardless of label. Additional outcomes become new rightward lanes.
        direct_primary_branch_ids = {
            edge["target"]
            for source_id in main_spine_node_ids
            for edge in outgoing[source_id]
            if edge["target"] not in main_spine_node_ids
        }
        continuation_edge_indices = {
            min(edge_list, key=lambda edge: edge["outcome_index"])["index"]
            for node_id, edge_list in outgoing.items()
            if node_id not in main_spine_node_ids and edge_list
        }
        locked_lane_by_id: Dict[str, int] = {
            node_id: 0 for node_id in main_spine_node_ids
        }
        locked_slots: set = set()
        for node_id in sorted(
            direct_primary_branch_ids,
            key=lambda item: (rank[item], node_order[item]),
        ):
            lane = 1
            while (rank[node_id], lane) in locked_slots:
                lane += 1
            locked_lane_by_id[node_id] = lane
            locked_slots.add((rank[node_id], lane))

        # Lock each branch's first XML-defined outcome to its parent's lane
        # before detached nodes and unrelated components are allocated.
        pending_locked_nodes = list(locked_lane_by_id)
        while pending_locked_nodes:
            source_id = pending_locked_nodes.pop(0)
            for edge in outgoing[source_id]:
                if edge["index"] not in continuation_edge_indices:
                    continue
                target_id = edge["target"]
                if target_id in main_spine_node_ids or target_id in locked_lane_by_id:
                    continue
                locked_lane_by_id[target_id] = locked_lane_by_id[source_id]
                pending_locked_nodes.append(target_id)

        visible_node_ids = (
            primary_node_ids if self.show_main_stream_only else set(node_map)
        )

        def lane_priority(node_id: str) -> int:
            if node_id in main_spine_node_ids:
                return 0
            if node_id in direct_primary_branch_ids:
                return 1
            if node_id in primary_node_ids:
                return 2
            if incoming[node_id]:
                return 3
            return 4

        lane_by_id: Dict[str, int] = {}
        occupied_slots: set = set()
        next_lane = 1
        lane_allocation_order = sorted(
            ordered_ids,
            key=lambda node_id: (lane_priority(node_id), rank[node_id], node_order[node_id]),
        )
        for node_id in lane_allocation_order:
            if node_id in locked_lane_by_id:
                lane_by_id[node_id] = locked_lane_by_id[node_id]
                occupied_slots.add((rank[node_id], locked_lane_by_id[node_id]))
                continue
            if node_id in main_spine_node_ids:
                lane_by_id[node_id] = 0
                occupied_slots.add((rank[node_id], 0))
                continue
            parent_id = tree_parent.get(node_id)
            parent_edge = next(
                (edge for edge in incoming[node_id]
                 if edge["index"] in tree_edge_indices),
                None,
            )
            if (
                parent_id is not None
                and parent_edge
                and parent_edge["index"] in continuation_edge_indices
                and parent_id not in main_spine_node_ids
                and parent_id in lane_by_id
            ):
                lane = lane_by_id[parent_id]
            else:
                if node_id in direct_primary_branch_ids:
                    lane = 1
                elif node_id in primary_node_ids:
                    lane = 2
                else:
                    primary_lanes = [
                        assigned_lane
                        for assigned_id, assigned_lane in lane_by_id.items()
                        if assigned_id in primary_node_ids
                    ]
                    lane = max(primary_lanes, default=1) + 1
                while (rank[node_id], lane) in occupied_slots:
                    lane += 1
                next_lane = max(next_lane, lane + 1)
            while (rank[node_id], lane) in occupied_slots:
                lane = next_lane
                next_lane += 1
            lane_by_id[node_id] = lane
            occupied_slots.add((rank[node_id], lane))

        primary_logical_lane_by_id = {
            node_id: lane_by_id[node_id]
            for node_id in primary_node_ids
        }

        # Reorder the tree lanes from the complete connection map. Dense
        # streams stay on the left; sparse streams move right without changing
        # the tree level or a node's parent-child relationship.
        connection_count = {
            node_id: len(outgoing[node_id]) + len(incoming[node_id])
            for node_id in node_map
        }
        lane_density: Dict[int, int] = {}
        lane_priority_by_lane: Dict[int, int] = {}
        for node_id, lane in lane_by_id.items():
            lane_density[lane] = lane_density.get(lane, 0) + connection_count[node_id]
            lane_priority_by_lane[lane] = min(
                lane_priority_by_lane.get(lane, lane_priority(node_id)),
                lane_priority(node_id),
            )
        auxiliary_lanes = sorted(
            (lane for lane in lane_density if lane != 0),
            key=lambda lane: (
                0 if lane == 1 and lane_priority_by_lane[lane] == 1 else 1,
                lane_priority_by_lane[lane],
                -lane_density[lane],
                lane,
            ),
        )
        lane_remap = {0: 0}
        lane_remap.update({lane: index + 1 for index, lane in enumerate(auxiliary_lanes)})
        lane_by_id = {
            node_id: lane_remap[lane]
            for node_id, lane in lane_by_id.items()
        }

        # Stream lanes are only required to be distinct while their nodes
        # coexist vertically. Reuse a display lane once an earlier stream has
        # ended, which prevents long scenarios from expanding indefinitely.
        lane_span: Dict[int, List[int]] = {}
        remapped_lane_density: Dict[int, int] = {}
        remapped_lane_priority: Dict[int, int] = {}
        for node_id, lane in lane_by_id.items():
            level = rank[node_id]
            span = lane_span.setdefault(lane, [level, level])
            span[0] = min(span[0], level)
            span[1] = max(span[1], level)
            remapped_lane_density[lane] = (
                remapped_lane_density.get(lane, 0) + connection_count[node_id]
            )
            remapped_lane_priority[lane] = min(
                remapped_lane_priority.get(lane, lane_priority(node_id)),
                lane_priority(node_id),
            )
        display_lane_end: List[int] = [lane_span[0][1]] if 0 in lane_span else []
        lane_display_remap: Dict[int, int] = {0: 0} if 0 in lane_span else {}
        for lane in sorted(
            (value for value in lane_span if value != 0),
            key=lambda value: (
                0 if value == 1 and remapped_lane_priority[value] == 1 else 1,
                lane_span[value][0],
                remapped_lane_priority[value],
                -remapped_lane_density[value],
                value,
            ),
        ):
            start_level, end_level = lane_span[lane]
            reusable = next(
                (index for index, occupied_end in enumerate(display_lane_end[1:], start=1)
                 if index != 1 and occupied_end < start_level),
                None,
            )
            if reusable is None:
                reusable = len(display_lane_end)
                display_lane_end.append(end_level)
            else:
                display_lane_end[reusable] = end_level
            lane_display_remap[lane] = reusable
        lane_by_id = {
            node_id: lane_display_remap[lane]
            for node_id, lane in lane_by_id.items()
        }
        lane_by_id.update(primary_logical_lane_by_id)

        primary_max_lane = max(
            (lane_by_id[node_id] for node_id in primary_node_ids),
            default=0,
        )
        unreachable_lane_remap = {
            lane: primary_max_lane + index + 1
            for index, lane in enumerate(sorted({
                lane_by_id[node_id]
                for node_id in start_unreachable_node_ids
            }))
        }
        for node_id in start_unreachable_node_ids:
            lane_by_id[node_id] = unreachable_lane_remap[lane_by_id[node_id]]

        # A column gap holds only the routed edges that cross its boundary.
        route_count_by_boundary: Dict[int, int] = {}
        for edge in edges:
            source_lane = lane_by_id[edge["source"]]
            target_lane = lane_by_id[edge["target"]]
            if source_lane == target_lane:
                continue
            for boundary in range(min(source_lane, target_lane), max(source_lane, target_lane)):
                route_count_by_boundary[boundary] = (
                    route_count_by_boundary.get(boundary, 0) + 1
                )
        lane_x: Dict[int, float] = {0: 100.0}
        for lane in range(1, max(lane_by_id.values(), default=0) + 1):
            previous_lane = lane - 1
            if previous_lane == 0:
                boundary_routes = route_count_by_boundary.get(0, 0)
                gap = 40 + max(0, boundary_routes - 1) * 10
            else:
                boundary_routes = route_count_by_boundary.get(previous_lane, 0)
                extra_lane_groups = max(0, math.ceil(math.sqrt(boundary_routes)) - 1)
                gap = 40 + extra_lane_groups * 20
            lane_x[lane] = lane_x[previous_lane] + W + gap

        # Reserve space only where a routed edge needs a horizontal segment:
        # immediately below its source or immediately above its destination.
        # A vertical segment crossing an intermediate level needs no extra row.
        routing_pressure_by_gap: Dict[int, int] = {}
        for edge in edges:
            source_level = rank[edge["source"]]
            target_level = rank[edge["target"]]
            is_straight_tree_edge = (
                edge["index"] in tree_edge_indices
                and edge["normal"]
                and lane_by_id[edge["source"]] == lane_by_id[edge["target"]]
                and target_level == source_level + 1
            )
            if is_straight_tree_edge:
                continue
            routing_pressure_by_gap[source_level] = (
                routing_pressure_by_gap.get(source_level, 0) + 1
            )
            if target_level > source_level:
                destination_gap = target_level - 1
                routing_pressure_by_gap[destination_gap] = (
                    routing_pressure_by_gap.get(destination_gap, 0) + 1
                )
        level_y: Dict[int, float] = {}
        current_y = 40.0
        for level in sorted(set(rank.values())):
            level_y[level] = current_y
            current_y += H + 30 + 10 * routing_pressure_by_gap.get(level, 0)

        # Keep each connected stream in its computed lane. This avoids packing
        # unrelated branches into one column and creating dense route bundles.
        # Only a node with no graph links can reuse an empty left slot.
        pos_map: Dict[str, QPointF] = {}
        slot_x = [lane_x[lane] for lane in sorted(lane_x)]
        nodes_by_level: Dict[int, List[str]] = {}
        for node_id in ordered_ids:
            nodes_by_level.setdefault(rank[node_id], []).append(node_id)
        for level, level_nodes in nodes_by_level.items():
            available_slots = list(slot_x)
            connected_nodes = sorted(
                (node_id for node_id in level_nodes if connection_count[node_id]),
                key=lambda node_id: (lane_by_id[node_id], node_order[node_id]),
            )
            for node_id in connected_nodes:
                preferred_x = lane_x[lane_by_id[node_id]]
                if preferred_x in available_slots:
                    candidate_x = preferred_x
                elif available_slots:
                    candidate_x = min(
                        available_slots,
                        key=lambda slot: (abs(slot - preferred_x), slot),
                    )
                else:
                    candidate_x = max(
                        position.x() for position in pos_map.values()
                    ) + W + 40
                    available_slots.append(candidate_x)
                pos_map[node_id] = QPointF(candidate_x, level_y[level])
                available_slots.remove(candidate_x)

        if self.use_display_layout:
            laid_out_nodes = [node for node in nodes if node.layout_info]
            if laid_out_nodes:
                min_x = min(node.layout_info["x"] for node in laid_out_nodes)
                min_y = min(node.layout_info["y"] for node in laid_out_nodes)
                placed_layout_nodes: List[str] = []
                for node in sorted(
                    laid_out_nodes,
                    key=lambda item: (item.layout_info["y"], item.layout_info["x"], node_order[item.id]),
                ):
                    target_x = 100 + node.layout_info["x"] - min_x
                    target_y = 40 + node.layout_info["y"] - min_y
                    while any(
                        target_y < pos_map[other_id].y() + H + 20
                        and target_y + H + 20 > pos_map[other_id].y()
                        and target_x < pos_map[other_id].x() + W + 20
                        and target_x + W + 20 > pos_map[other_id].x()
                        for other_id in placed_layout_nodes
                    ):
                        target_x += W + 20
                    pos_map[node.id] = QPointF(target_x, target_y)
                    placed_layout_nodes.append(node.id)

        # Any unobstructed same-column downward edge is shorter as a direct
        # vertical route. Parallel edges receive separate 10px port slots.
        direct_edge_indices: set = set()
        direct_port_slot_by_edge: Dict[int, int] = {}
        direct_slots_by_source: Dict[str, set] = {}
        direct_slots_by_target: Dict[str, set] = {}
        for edge in sorted(edges, key=edge_key):
            source_id, target_id = edge["source"], edge["target"]
            source_pos, target_pos = pos_map[source_id], pos_map[target_id]
            x_alignment_tolerance = (W / 2 - 10) if self.use_display_layout else 1
            same_column = abs(source_pos.x() - target_pos.x()) <= x_alignment_tolerance
            if target_pos.y() <= source_pos.y() or not same_column:
                continue
            is_clear = not any(
                other_id not in {source_id, target_id}
                and pos_map[other_id].x() - 10 <= source_pos.x() + W / 2 <= pos_map[other_id].x() + W + 10
                and pos_map[other_id].y() - 10 < target_pos.y()
                and pos_map[other_id].y() + H + 10 > source_pos.y() + H
                for other_id in pos_map
            )
            if not is_clear:
                continue
            source_slots = direct_slots_by_source.setdefault(source_id, set())
            target_slots = direct_slots_by_target.setdefault(target_id, set())
            slot = next(index for index in range(len(edges)) if index not in source_slots and index not in target_slots)
            direct_edge_indices.add(edge["index"])
            direct_port_slot_by_edge[edge["index"]] = slot
            source_slots.add(slot)
            target_slots.add(slot)
        for node_id in pos_map:
            if node_id not in visible_node_ids:
                continue
            item = GraphicsNodeItem(node_map[node_id], scope_prefix, viewer=self)
            item.setPos(pos_map[node_id])
            self.scene.addItem(item)
            self.node_items[node_id] = item

        edges = [
            edge for edge in edges
            if edge["source"] in visible_node_ids and edge["target"] in visible_node_ids
        ]
        visible_positions = [
            pos_map[node_id]
            for node_id in visible_node_ids
            if node_id in pos_map
        ]
        min_left = min(position.x() for position in visible_positions)
        max_right = max(position.x() + W for position in visible_positions)
        if self.use_display_layout:
            # Original layout coordinates do not share the automatic lane_x
            # grid. Search every visible 10px corridor and let obstacle checks
            # select the nearest short route through the actual empty space.
            track_candidates = [
                min_left - 20 + index * 10
                for index in range(int((max_right - min_left + 40) / 10) + 1)
            ]
            track_candidates.extend(
                [min_left - 30 - index * 10 for index in range(len(edges))] +
                [max_right + 30 + index * 10 for index in range(len(edges))]
            )
        else:
            column_x = sorted(set(lane_x.values()))
            track_candidates = []
            for left_x, right_x in zip(column_x, column_x[1:]):
                candidate_x = left_x + W + 20
                while candidate_x <= right_x - 20:
                    track_candidates.append(candidate_x)
                    candidate_x += 10
            track_candidates.extend(
                [min_left - 20 - index * 10 for index in range(len(edges))] +
                [max_right + 20 + index * 10 for index in range(len(edges))]
            )
        edges.sort(
            key=lambda edge: (
                node_order[edge["target"]],
                abs(pos_map[edge["source"]].x() - pos_map[edge["target"]].x()),
                edge_key(edge),
            )
        )
        source_port_index: Dict[str, int] = {}
        destination_port_index: Dict[str, int] = {}
        source_port_slots: Dict[str, set] = {}
        destination_port_slots: Dict[str, set] = {}
        destination_side_port_index: Dict[str, int] = {}
        for edge in edges:
            if edge["index"] in direct_edge_indices:
                slot = direct_port_slot_by_edge[edge["index"]]
                source_port_slots.setdefault(edge["source"], set()).add(slot)
                destination_port_slots.setdefault(edge["target"], set()).add(slot)
                source_port_index[edge["source"]] = max(source_port_index.get(edge["source"], 0), slot + 1)
                destination_port_index[edge["target"]] = max(destination_port_index.get(edge["target"], 0), slot + 1)
        level_exit_index: Dict[int, int] = {}
        used_track_ranges: Dict[float, List[tuple]] = {}
        used_approach_segments: List[tuple] = []
        used_approach_y_by_level: Dict[int, List[float]] = {}
        self.child_route_debug: List[Dict[str, object]] = []

        def port_offset(index: int) -> float:
            if index == 0:
                return 0.0
            step = (index + 1) // 2
            return 10.0 * step * (1 if index % 2 else -1)

        for edge in edges:
            source_id = edge["source"]
            target_id = edge["target"]
            source_pos = pos_map[source_id]
            target_pos = pos_map[target_id]

            if edge["index"] in direct_edge_indices:
                port_slot = direct_port_slot_by_edge[edge["index"]]
                port_x = port_offset(port_slot)
                direct_x = target_pos.x() + W / 2 + port_x
                p1 = QPointF(direct_x, source_pos.y() + H)
                p2 = QPointF(direct_x, target_pos.y())
                color = COL_NORMAL if edge["normal"] else COL_EXCEP
                path = QPainterPath()
                path.moveTo(p1)
                path.lineTo(p2)
                connector_item = self._paint(path, color)
                self._register_connector(source_id, target_id, connector_item, color)
                self._arrow(p2, "down", color)
                label_step = (port_slot + 2) // 2
                label_y = (-12 if port_slot % 2 == 0 else 12) * label_step
                self._label(str(edge["label"]), QPointF(p1.x() + 22, (p1.y() + p2.y()) / 2 + label_y), color)
                self.child_route_debug.append({
                    "edge_index": edge["index"],
                    "tree_edge": edge["index"] in tree_edge_indices,
                    "points": (p1, p2),
                })
                continue

            used_source_slots = source_port_slots.setdefault(source_id, set())
            source_slot = source_port_index.get(source_id, 0)
            while source_slot in used_source_slots:
                source_slot += 1
            used_source_slots.add(source_slot)
            source_port_index[source_id] = source_slot + 1

            source_level = rank[source_id]
            target_level = rank[target_id]

            # In displayInformation mode, a clear vertical drop from the
            # source is shorter than detouring through a distant lane. Route
            # down at the source X, turn once just above the destination, and
            # enter through the destination top.
            if self.use_display_layout and target_pos.y() > source_pos.y():
                source_center_x = source_pos.x() + W / 2 + port_offset(source_slot)
                approach_y = target_pos.y() - 12
                corridor_is_clear = not any(
                    other_id not in {source_id, target_id}
                    and pos_map[other_id].x() - 10 <= source_center_x <= pos_map[other_id].x() + W + 10
                    and pos_map[other_id].y() - 10 < approach_y
                    and pos_map[other_id].y() + H + 10 > source_pos.y() + H
                    for other_id in pos_map
                )
                if corridor_is_clear:
                    level_approach_y = used_approach_y_by_level.setdefault(target_level, [])
                    while any(abs(approach_y - used_y) < 5 for used_y in level_approach_y):
                        approach_y -= 5
                    level_approach_y.append(approach_y)
                    used_target_slots = destination_port_slots.setdefault(target_id, set())
                    target_slot = destination_port_index.get(target_id, 0)
                    while target_slot in used_target_slots:
                        target_slot += 1
                    used_target_slots.add(target_slot)
                    destination_port_index[target_id] = target_slot + 1
                    target_center_x = target_pos.x() + W / 2 + port_offset(target_slot)
                    p1 = QPointF(source_center_x, source_pos.y() + H)
                    p2 = QPointF(source_center_x, approach_y)
                    p3 = QPointF(target_center_x, approach_y)
                    p4 = QPointF(target_center_x, target_pos.y())
                    color = COL_NORMAL if edge["normal"] else COL_EXCEP
                    path = QPainterPath()
                    path.moveTo(p1)
                    for point in (p2, p3, p4):
                        path.lineTo(point)
                    connector_item = self._paint(path, color)
                    self._register_connector(source_id, target_id, connector_item, color)
                    self._arrow(p4, "down", color)
                    self._label(str(edge["label"]), QPointF(p1.x() + 18, p1.y() + 12), color)
                    self.child_route_debug.append({
                        "edge_index": edge["index"],
                        "tree_edge": edge["index"] in tree_edge_indices,
                        "points": (p1, p2, p3, p4),
                    })
                    continue

            used_target_slots = destination_port_slots.setdefault(target_id, set())
            target_slot = destination_port_index.get(target_id, 0)
            while target_slot in used_target_slots:
                target_slot += 1
            used_target_slots.add(target_slot)
            destination_port_index[target_id] = target_slot + 1
            exit_index = level_exit_index.get(source_level, 0)
            level_exit_index[source_level] = exit_index + 1

            p1 = QPointF(source_pos.x() + W / 2 + port_offset(source_slot), source_pos.y() + H)
            p2 = QPointF(p1.x(), p1.y() + 12 + exit_index * 10)
            approach_y = target_pos.y() - 12

            def track_is_clear(track_x: float) -> bool:
                vertical_top = min(p2.y(), approach_y)
                vertical_bottom = max(p2.y(), approach_y)
                if any(
                    other_id not in {source_id, target_id}
                    and pos_map[other_id].x() - 10 <= track_x <= pos_map[other_id].x() + W + 10
                    and pos_map[other_id].y() - 10 <= vertical_bottom
                    and pos_map[other_id].y() + H + 10 >= vertical_top
                    for other_id in pos_map
                ):
                    return False
                return all(
                    vertical_bottom + 10 <= reserved_top or vertical_top - 10 >= reserved_bottom
                    for reserved_top, reserved_bottom in used_track_ranges.get(track_x, [])
                )

            if target_pos.x() > source_pos.x():
                internal_candidates = [
                    candidate for candidate in track_candidates
                    if source_pos.x() + W + 10 <= candidate <= target_pos.x() - 10
                ]
                fallback_candidates = [
                    candidate for candidate in track_candidates
                    if candidate >= target_pos.x() + W + 10
                ]
            elif target_pos.x() < source_pos.x():
                internal_candidates = [
                    candidate for candidate in track_candidates
                    if target_pos.x() + W + 10 <= candidate <= source_pos.x() - 10
                ]
                fallback_candidates = [
                    candidate for candidate in track_candidates
                    if candidate <= target_pos.x() - 10
                ]
            else:
                internal_candidates = [
                    candidate for candidate in track_candidates
                    if candidate >= source_pos.x() + W + 10
                ]
                fallback_candidates = [
                    candidate for candidate in track_candidates
                    if candidate >= source_pos.x() + W + 10
                ]
            directional_candidates = [
                candidate for candidate in internal_candidates if track_is_clear(candidate)
            ]
            if not directional_candidates:
                directional_candidates = [
                    candidate for candidate in fallback_candidates if track_is_clear(candidate)
                ]
            if self.use_display_layout:
                # In original-coordinate mode, choose the actual shortest
                # orthogonal route through the visible free space rather than
                # retaining any automatic-column preference.
                track_x = min(
                    directional_candidates,
                    key=lambda candidate: (
                        abs(p2.x() - candidate)
                        + abs(candidate - (target_pos.x() + W / 2))
                        + abs(p2.y() - approach_y)
                    ),
                )
            else:
                track_x = min(
                    directional_candidates,
                    key=lambda candidate: abs(p2.x() - candidate) + abs(candidate - (target_pos.x() + W / 2)),
                )

            def approach_is_clear(candidate_y: float) -> bool:
                approach_left = min(track_x, target_pos.x() + W / 2)
                approach_right = max(track_x, target_pos.x() + W / 2)
                if any(abs(candidate_y - used_y) < 5 for used_y in used_approach_y_by_level.get(target_level, [])):
                    return False
                return not any(
                    abs(candidate_y - used_y) < 5
                    and approach_left <= max(used_left, used_right)
                    and approach_right >= min(used_left, used_right)
                    for used_y, used_left, used_right in used_approach_segments
                )

            while not approach_is_clear(approach_y):
                approach_y -= 5
            used_approach_y_by_level.setdefault(target_level, []).append(approach_y)
            used_track_ranges.setdefault(track_x, []).append(
                (min(p2.y(), approach_y), max(p2.y(), approach_y))
            )
            used_approach_segments.append(
                (approach_y, track_x, target_pos.x() + W / 2)
            )
            p3 = QPointF(track_x, p2.y())
            p4 = QPointF(track_x, approach_y)
            p5 = QPointF(target_pos.x() + W / 2 + port_offset(target_slot), p4.y())
            p6 = QPointF(p5.x(), target_pos.y())

            path = QPainterPath()
            path.moveTo(p1)
            for point in (p2, p3, p4, p5, p6):
                path.lineTo(point)
            color = COL_NORMAL if edge["normal"] else COL_EXCEP
            connector_item = self._paint(path, color)
            self._register_connector(source_id, target_id, connector_item, color)
            self._arrow(p6, "down", color)
            self._label(str(edge["label"]), QPointF(p2.x() + 18, p2.y() - 13), color)
            self.child_route_debug.append({
                "edge_index": edge["index"],
                "tree_edge": edge["index"] in tree_edge_indices,
                "points": (p1, p2, p3, p4, p5, p6),
            })

        self.scene.setSceneRect(
            self.scene.itemsBoundingRect().adjusted(-100, -60, 120, 60)
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Node click handler
    # ═══════════════════════════════════════════════════════════════════════════
    def handle_node_click(self, item: GraphicsNodeItem):
        if self.selected_item:
            self.selected_item.set_node_selected(False)
        self._clear_connector_highlight()
        self.selected_item = item
        item.set_node_selected(True)
        self._highlight_connected_connectors(item.node.id)
        self.node_selected.emit(item.node)

    def handle_node_double_click(self, item: GraphicsNodeItem):
        if item.node.child_actions:
            self.compound_selected.emit(item.node)

    def center_selected_node(self):
        if self.selected_item:
            self.view.centerOn(self.selected_item)

    # ═══════════════════════════════════════════════════════════════════════════
    # Connector A: Straight vertical ↓  (green — OK / Logged / Assigned / …)
    #
    #   bottom-centre of src ──────────────────── top-centre of dst
    # ═══════════════════════════════════════════════════════════════════════════
    def _conn_straight(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                       label: str):
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp, dp = src.pos(), dst.pos()
        p1 = QPointF(sp.x() + W / 2, sp.y() + H)   # bottom center
        p2 = QPointF(dp.x() + W / 2, dp.y())         # top center
        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2)
        self._paint(path, COL_NORMAL)
        self._arrow(p2, "down", COL_NORMAL)
        # Label to the RIGHT of the line, at mid height — never on the line
        mid_y = (p1.y() + p2.y()) / 2
        self._label(label, QPointF(p1.x() + 22, mid_y - 8), COL_NORMAL)

    # ═══════════════════════════════════════════════════════════════════════════
    # Connector B: True — exits LEFT at the two-thirds anchor, then hooks right/down  (green)
    #
    #   p1 ◄──── p2          horizontal (exits src LEFT at two-thirds height)
    #            │            vertical   (unique left track_x)
    #           p3 ────► p4
    #                    │   vertical (enters a lower dst TOP center)
    #                    ▼ p5
    #
    # track_x < NX (to the left of all nodes)
    # ═══════════════════════════════════════════════════════════════════════════
    def _conn_true(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                   label: str, track_x: float):
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp, dp = src.pos(), dst.pos()
        exit_y = sp.y() + (2 * H) / 3
        enters_from_above = dp.y() > sp.y()

        p1 = QPointF(sp.x(),  exit_y)            # src LEFT two-thirds anchor
        p2 = QPointF(track_x, exit_y)            # ← go left to track
        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2)

        if enters_from_above:
            approach_y = dp.y() - 16
            p3 = QPointF(track_x, approach_y)         # ↓ to above destination
            p4 = QPointF(dp.x() + W / 4, approach_y)  # → align left of top center
            p5 = QPointF(dp.x() + W / 4, dp.y())      # ↓ enter from above
            path.lineTo(p3); path.lineTo(p4); path.lineTo(p5)
            arrow_tip, direction = p5, "down"
        else:
            p3 = QPointF(track_x, dp.y() + H / 2)     # ↓/↑ to destination level
            p4 = QPointF(dp.x(), dp.y() + H / 2)      # → enter from left
            path.lineTo(p3); path.lineTo(p4)
            arrow_tip, direction = p4, "right"

        self._paint(path, COL_NORMAL)
        self._arrow(arrow_tip, direction, COL_NORMAL)
        # Label above the horizontal exit segment, midway between node edge and track
        mid_x = (sp.x() + track_x) / 2
        self._label(label, QPointF(mid_x, exit_y - 13), COL_NORMAL)

    def _conn_normal_branch(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                            label: str, bus_x: float, approach_index: int = 0):
        """Route a normal main-to-auxiliary transition into the right column."""
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp, dp = src.pos(), dst.pos()
        exit_y = sp.y() + H / 2
        approach_y = dp.y() - 16 - approach_index * 12
        entry_x = dp.x() + (W / 4 if bus_x < dp.x() + W / 2 else 3 * W / 4)

        p1 = QPointF(sp.x() + W, exit_y)
        p2 = QPointF(bus_x, exit_y)
        p3 = QPointF(bus_x, approach_y)
        p4 = QPointF(entry_x, approach_y)
        p5 = QPointF(entry_x, dp.y())
        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2); path.lineTo(p3); path.lineTo(p4); path.lineTo(p5)
        self._paint(path, COL_NORMAL)
        self._arrow(p5, "down", COL_NORMAL)
        self._label(label, QPointF(sp.x() + W + 12, exit_y - 13), COL_NORMAL)

    # ═══════════════════════════════════════════════════════════════════════════
    # Connector C: False/Fail — exits RIGHT LOWER (Y + 2H/3)  →  (red)
    #
    #   p1 ──────────► p2          horizontal (exits at upper-right of src)
    #                  │            vertical   (unique right bus_x)
    #   p3 ──────────► p4
    #                  │                      vertical (enters lower dst TOP)
    #                  ▼ p5
    #
    # Label placed ABOVE the upper-right exit line (no overlap with Timeout label
    # which appears BELOW the lower-right exit from the same node).
    # ═══════════════════════════════════════════════════════════════════════════
    def _conn_false(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                    label: str, bus_x: float):
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp   = src.pos()
        H2   = (2 * H) // 3    # ≈29 px — lower-right exit offset
        exit_y = sp.y() + H2

        p1 = QPointF(sp.x() + W, exit_y)           # RIGHT LOWER exit
        p2 = QPointF(bus_x,      exit_y)            # → to bus track
        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2)
        if dst.pos().y() > sp.y():
            approach_y = dst.pos().y() - 16
            entry_x = dst.pos().x() + (W / 4 if bus_x < dst.pos().x() + W / 2 else 3 * W / 4)
            p3 = QPointF(bus_x, approach_y)
            p4 = QPointF(entry_x, approach_y)
            p5 = QPointF(entry_x, dst.pos().y())
            path.lineTo(p3); path.lineTo(p4); path.lineTo(p5)
            arrow_tip, direction = p5, "down"
        else:
            entry_y = dst.pos().y() + H / 2
            enters_from_left = bus_x < dst.pos().x() + W / 2
            p3 = QPointF(bus_x, entry_y)
            p4 = QPointF(dst.pos().x() if enters_from_left else dst.pos().x() + W,
                         entry_y)
            path.lineTo(p3); path.lineTo(p4)
            arrow_tip, direction = p4, "right" if enters_from_left else "left"
        self._paint(path, COL_EXCEP)
        self._arrow(arrow_tip, direction, COL_EXCEP)
        # Label BELOW the lower-right exit (Y + 4) → clearly below the line
        self._label(label, QPointF(sp.x() + W + 5, exit_y + 4), COL_EXCEP)

    # ═══════════════════════════════════════════════════════════════════════════
    # Connector D: Timeout — exits RIGHT UPPER (Y + H/3)  →  (red)
    #
    # Same shape as False but exits at UPPER-RIGHT of the source box.
    # → Timeout label (upper) and False label (lower) are ≥30 px apart
    #   even from the same node, so they NEVER overlap.
    # ═══════════════════════════════════════════════════════════════════════════
    def _conn_timeout(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                      label: str, bus_x: float):
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp   = src.pos()
        H1   = H // 3         # ≈14 px — upper-right exit offset
        exit_y = sp.y() + H1

        p1 = QPointF(sp.x() + W, exit_y)           # RIGHT UPPER exit
        p2 = QPointF(bus_x,      exit_y)            # → to bus track
        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2)
        if dst.pos().y() > sp.y():
            approach_y = dst.pos().y() - 16
            entry_x = dst.pos().x() + (W / 4 if bus_x < dst.pos().x() + W / 2 else 3 * W / 4)
            p3 = QPointF(bus_x, approach_y)
            p4 = QPointF(entry_x, approach_y)
            p5 = QPointF(entry_x, dst.pos().y())
            path.lineTo(p3); path.lineTo(p4); path.lineTo(p5)
            arrow_tip, direction = p5, "down"
        else:
            entry_y = dst.pos().y() + H / 2
            enters_from_left = bus_x < dst.pos().x() + W / 2
            p3 = QPointF(bus_x, entry_y)
            p4 = QPointF(dst.pos().x() if enters_from_left else dst.pos().x() + W,
                         entry_y)
            path.lineTo(p3); path.lineTo(p4)
            arrow_tip, direction = p4, "right" if enters_from_left else "left"
        self._paint(path, COL_EXCEP)
        self._arrow(arrow_tip, direction, COL_EXCEP)
        # Label ABOVE the upper-right exit (Y - 12) → clearly above the line
        self._label(label, QPointF(sp.x() + W + 5, exit_y - 12), COL_EXCEP)

    # ═══════════════════════════════════════════════════════════════════════════
    # Connector E: Return — exception col → normal col  (blue)
    #
    #   p1 ──────────► p2          horizontal (exits RIGHT CENTER of src)
    #                  │            vertical   (unique outer return bus_x)
    #   p4 ◄────────── p3          horizontal (enters RIGHT CENTER of dst)
    # ═══════════════════════════════════════════════════════════════════════════
    def _conn_return(self, src: GraphicsNodeItem, dst: GraphicsNodeItem,
                     label: str, bus_x: float):
        W, H = src.NODE_WIDTH, src.NODE_HEIGHT
        sp, dp = src.pos(), dst.pos()

        p1 = QPointF(sp.x() + W, sp.y() + H / 2)  # src RIGHT center
        p2 = QPointF(bus_x,      sp.y() + H / 2)  # → outer return bus
        p3 = QPointF(bus_x,      dp.y() + H / 2)  # ↑/↓ to dst level
        p4 = QPointF(dp.x() + W, dp.y() + H / 2)  # ← dst RIGHT center

        path = QPainterPath()
        path.moveTo(p1); path.lineTo(p2); path.lineTo(p3); path.lineTo(p4)
        self._paint(path, COL_RETURN)
        self._arrow(p4, "left", COL_RETURN)
        # Label above the exit, just past node right edge
        self._label(label, QPointF(sp.x() + W + 5, sp.y() + H / 2 - 13), COL_RETURN)

    # ═══════════════════════════════════════════════════════════════════════════
    # Drawing primitives
    # ═══════════════════════════════════════════════════════════════════════════
    def _paint(self, path: QPainterPath, color: QColor):
        item = QGraphicsPathItem(path)
        item.setZValue(0)
        item.setPen(QPen(color, 2))
        self.scene.addItem(item)
        return item

    def _register_connector(self, source_id: str, target_id: str,
                            item: QGraphicsPathItem, color: QColor):
        self.connector_items_by_source.setdefault(source_id, []).append((item, color))
        self.connector_items_by_target.setdefault(target_id, []).append((item, color))

    def _clear_connector_highlight(self):
        for item, color in self.highlighted_connector_items:
            item.setPen(QPen(color, 2))
            item.setZValue(0)
        self.highlighted_connector_items.clear()

    def _highlight_connected_connectors(self, node_id: str):
        seen_items = set()
        connectors = (
            self.connector_items_by_source.get(node_id, []) +
            self.connector_items_by_target.get(node_id, [])
        )
        for item, color in connectors:
            if item in seen_items:
                continue
            seen_items.add(item)
            item.setPen(QPen(color.lighter(125), 4))
            item.setZValue(1)
            self.highlighted_connector_items.append((item, color))

    def _label(self, text: str, pos: QPointF, color: QColor):
        text = text.strip()
        if not text:
            return
        t = QGraphicsTextItem(text)
        t.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        t.setZValue(3)
        t.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
        t.setDefaultTextColor(color)
        r = t.boundingRect()
        t.setPos(pos.x() - r.width() / 2, pos.y() - r.height() / 2)
        self.scene.addItem(t)

    def _arrow(self, tip: QPointF, direction: str, color: QColor):
        """Solid filled triangle arrow at the connector tip."""
        s = 8.0
        path = QPainterPath()
        if direction == "down":
            path.moveTo(tip)
            path.lineTo(tip.x() - s/2, tip.y() - s)
            path.lineTo(tip.x() + s/2, tip.y() - s)
        elif direction == "right":
            path.moveTo(tip)
            path.lineTo(tip.x() - s, tip.y() - s/2)
            path.lineTo(tip.x() - s, tip.y() + s/2)
        elif direction == "left":
            path.moveTo(tip)
            path.lineTo(tip.x() + s, tip.y() - s/2)
            path.lineTo(tip.x() + s, tip.y() + s/2)
        path.closeSubpath()
        item = QGraphicsPathItem(path)
        item.setZValue(2)
        item.setBrush(QBrush(color))
        item.setPen(QPen(color, 1))
        self.scene.addItem(item)
