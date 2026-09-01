import os
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QSplitterHandle, QFileDialog, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen

from anritsu_parser import parse_anritsu_test_file, AnritsuScenario, AnritsuNode
from flowchart_viewer import FlowchartViewer
from parameter_tree import ParameterTreeWidget
from version import APP_NAME, VERSION

class CustomSplitterHandle(QSplitterHandle):
    """Custom splitter handle with visible affordance dots and hover highlight."""
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(
            Qt.CursorShape.SizeVerCursor if orientation == Qt.Orientation.Vertical else Qt.CursorShape.SizeHorCursor
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        is_hover = self.underMouse()
        
        # Background
        bg_color = QColor(74, 144, 226, 200) if is_hover else QColor(225, 228, 234)
        painter.fillRect(rect, bg_color)
        
        # Border & Grip
        border_color = QColor(42, 112, 194) if is_hover else QColor(195, 200, 208)
        grip_color = QColor(255, 255, 255) if is_hover else QColor(135, 142, 153)
        painter.setBrush(QBrush(grip_color))

        cx = rect.center().x()
        cy = rect.center().y()

        if self.orientation() == Qt.Orientation.Vertical:
            painter.setPen(border_color)
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            painter.setPen(grip_color)
            for dx in [-24, -12, 0, 12, 24]:
                painter.drawEllipse(int(cx + dx - 1), int(cy - 1), 3, 3)
        else:
            painter.setPen(border_color)
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            painter.setPen(grip_color)
            for dy in [-24, -12, 0, 12, 24]:
                painter.drawEllipse(int(cx - 1), int(cy + dy - 1), 3, 3)

class VisualSplitter(QSplitter):
    """QSplitter with custom visually distinguishable handle."""
    def __init__(self, orientation, parent=None, handle_width=7):
        super().__init__(orientation, parent)
        self.setHandleWidth(handle_width)

    def createHandle(self):
        return CustomSplitterHandle(self.orientation(), self)

class AnritsuScenarioViewerWindow(QMainWindow):
    """Main window with nested child-scope navigation."""
    def __init__(self, default_file: Optional[str] = None):
        super().__init__()
        self.scenario: Optional[AnritsuScenario] = None
        self.current_selected_node: Optional[AnritsuNode] = None
        self.current_scope_prefix = "root"
        
        # Navigation Stack for Child Scopes: List of (node, scope_prefix)
        self.child_scope_stack: List[Tuple[AnritsuNode, str]] = []

        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(1300, 850)

        self._init_ui()

        if default_file and os.path.exists(default_file):
            self.load_scenario_file(default_file)

    def _init_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 1. Top Control Bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(4, 2, 4, 2)

        self.btn_open = QPushButton("Open Scenario File")
        font = QFont("Malgun Gothic", 9, QFont.Weight.Bold)
        self.btn_open.setFont(font)
        self.btn_open.setMinimumHeight(30)
        self.btn_open.clicked.connect(self._on_open_file_clicked)

        self.lbl_file_path = QLabel("No file loaded")
        self.lbl_file_path.setStyleSheet("color: #555555; padding-left: 10px;")

        top_bar.addWidget(self.btn_open)
        top_bar.addWidget(self.lbl_file_path, stretch=1)

        main_layout.addLayout(top_bar)

        # 2. Main Horizontal Splitter (Left: Flowcharts, Right: Parameter Inspector)
        self.main_splitter = VisualSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Left Vertical Splitter (Upper: Main Scope, Lower: Child Scope)
        self.left_splitter = VisualSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setChildrenCollapsible(False)

        self.main_flow_viewer = FlowchartViewer(title="Main Scope: root")
        self.child_flow_viewer = FlowchartViewer(title="Child Scope: (None)")
        self.child_flow_viewer.btn_close.setVisible(True)
        self.child_flow_viewer.btn_close.setText("Close Child Scope")
        self.child_flow_viewer.btn_close.clicked.connect(self._on_close_or_back_child_scope)

        self.left_splitter.addWidget(self.main_flow_viewer)
        self.left_splitter.addWidget(self.child_flow_viewer)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 1)

        # Force minimum width so Qt layout engine can NEVER collapse the flowchart pane
        self.left_splitter.setMinimumWidth(550)

        # Initially hide the child scope pane
        self.child_flow_viewer.setVisible(False)

        # Right Parameter Inspector Panel
        self.param_tree = ParameterTreeWidget()
        self.param_tree.setMinimumWidth(350)

        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.param_tree)
        
        # Set stable left/right ratio (Left: 60%, Right: 40%)
        self.main_splitter.setStretchFactor(0, 6)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setSizes([780, 480])

        main_layout.addWidget(self.main_splitter, stretch=1)

        # Signal Connections
        self.main_flow_viewer.node_selected.connect(self._on_main_node_selected)
        self.main_flow_viewer.compound_selected.connect(self._on_main_compound_selected)

        self.child_flow_viewer.node_selected.connect(self._on_child_node_selected)
        self.child_flow_viewer.compound_selected.connect(self._on_child_compound_selected)
        self.main_flow_viewer.find_requested.connect(self._on_main_search_requested)
        self.child_flow_viewer.find_requested.connect(self._on_child_search_requested)
        self.param_tree.display_layout_toggled.connect(self._on_display_layout_toggled)
        self.param_tree.detail_toggled.connect(self._on_detail_toggled)
        self.param_tree.main_stream_only_toggled.connect(self._on_main_stream_only_toggled)

    def _on_open_file_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Anritsu Scenario File", "", "Anritsu Test Files (*.test);;XML Files (*.xml);;All Files (*)"
        )
        if file_path:
            self.load_scenario_file(file_path)

    def load_scenario_file(self, file_path: str):
        try:
            self.scenario = parse_anritsu_test_file(file_path)
            file_name = os.path.basename(file_path)
            self.lbl_file_path.setText(f"File: {file_name} ({file_path})")
            self.param_tree.set_file_info(file_name)

            # Display Main Scope Flowchart
            self.main_flow_viewer.set_scope(self.scenario.root_actions, scope_prefix="root")
            
            # Reset Child Scope Navigation Stack & Inspector
            self.child_scope_stack.clear()
            self._close_child_scope()
            self.param_tree.display_node_info(None)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load scenario file:\n{str(e)}")

    def _on_main_node_selected(self, node: AnritsuNode):
        self.current_selected_node = node
        self.current_scope_prefix = "root"
        self.param_tree.display_node_info(node, scope_prefix="root")

    def _on_main_compound_selected(self, node: AnritsuNode):
        self.main_flow_viewer.edit_search.setText(node.id)
        if node.child_actions:
            scope_prefix = f"root:{node.id}"
            # Reset stack to level 1
            self.child_scope_stack = [(node, scope_prefix)]
            
            self._update_child_scope_ui()

    def _on_child_compound_selected(self, node: AnritsuNode):
        self.child_flow_viewer.edit_search.setText(node.id)
        if node.child_actions:
            # Push nested compound node to navigation stack
            parent_prefix = self.child_scope_stack[-1][1] if self.child_scope_stack else "root"
            child_prefix = f"{parent_prefix}:{node.id}"
            self.child_scope_stack.append((node, child_prefix))
            
            self._update_child_scope_ui()

    def _update_child_scope_ui(self):
        if not self.child_scope_stack:
            self._close_child_scope()
            return

        child_was_visible = self.child_flow_viewer.isVisible()
        curr_node, curr_prefix = self.child_scope_stack[-1]
        scope_name = f"Child Scope: {curr_prefix} - {curr_node.name}"
        
        self.child_flow_viewer.title_str = scope_name
        self.child_flow_viewer.set_scope(curr_node.child_actions, scope_prefix=curr_prefix)
        self.child_flow_viewer.setVisible(True)

        # Update button text based on stack depth
        if len(self.child_scope_stack) > 1:
            self.child_flow_viewer.btn_close.setText("Back to Parent Scope")
        else:
            self.child_flow_viewer.btn_close.setText("Close Child Scope")

        # Use a balanced default only when opening the child pane. Subsequent
        # compound navigation keeps the user's manually adjusted pane ratio.
        if not child_was_visible:
            self.left_splitter.setSizes([450, 450])

        # Enforce horizontal splitter ratio (Left: 60%, Right: 40%)
        total_w = self.main_splitter.width()
        if total_w > 700:
            self.main_splitter.setSizes([int(total_w * 0.6), int(total_w * 0.4)])

    def _on_child_node_selected(self, node: AnritsuNode):
        self.current_selected_node = node
        scope_prefix = self.child_flow_viewer.current_scope_prefix
        self.param_tree.display_node_info(node, scope_prefix=scope_prefix)

    def _on_display_layout_toggled(self, enabled: bool):
        self.main_flow_viewer.set_use_display_layout(enabled)
        self.child_flow_viewer.set_use_display_layout(enabled)

        if self.scenario:
            self.main_flow_viewer.set_scope(self.scenario.root_actions, scope_prefix="root")
        if self.child_scope_stack:
            self._update_child_scope_ui()

    def _on_detail_toggled(self, enabled: bool):
        self.main_flow_viewer.set_show_detail(enabled)
        self.child_flow_viewer.set_show_detail(enabled)
        if self.scenario:
            self.main_flow_viewer.set_scope(self.scenario.root_actions, scope_prefix="root")
        if self.child_scope_stack:
            self._update_child_scope_ui()

    def _on_main_stream_only_toggled(self, enabled: bool):
        self.main_flow_viewer.set_show_main_stream_only(enabled)
        self.child_flow_viewer.set_show_main_stream_only(enabled)
        if self.scenario:
            self.main_flow_viewer.set_scope(self.scenario.root_actions, scope_prefix="root")
        if self.child_scope_stack:
            self._update_child_scope_ui()

    def _on_close_or_back_child_scope(self):
        if not self.child_scope_stack:
            return

        popped_node, _ = self.child_scope_stack.pop()

        if self.child_scope_stack:
            # Pop nested scope and return to parent child scope
            self._update_child_scope_ui()
            # Select and center the compound node that was just exited
            self.child_flow_viewer.select_and_center_node(popped_node.id)
        else:
            # Close child scope completely and return to main scope
            self._close_child_scope()
            # Select and center the root compound node in main flow viewer
            self.main_flow_viewer.select_and_center_node(popped_node.id)

    def _close_child_scope(self):
        self.child_flow_viewer.title_str = "Child Scope: (None)"
        self.child_flow_viewer.set_scope([], scope_prefix="")
        self.child_flow_viewer.setVisible(False)

        total_w = self.main_splitter.width()
        if total_w > 700:
            self.main_splitter.setSizes([int(total_w * 0.6), int(total_w * 0.4)])

    def _on_main_search_requested(self, query: str):
        self._handle_search(query, from_viewer="main")

    def _on_child_search_requested(self, query: str):
        self._handle_search(query, from_viewer="child")

    def _handle_search(self, query: str, from_viewer: str = "main"):
        if not self.scenario:
            QMessageBox.information(self, "Find Node", "No scenario file loaded.")
            return

        raw_parts = [p.strip() for p in query.split(":") if p.strip()]
        if not raw_parts:
            return

        # Strip optional 'root' prefix
        if raw_parts[0].lower() == "root":
            parts = raw_parts[1:]
        else:
            parts = raw_parts

        if not parts:
            parts = ["0"]

        # Case 1: Search from Child Scope and query is a single node ID (e.g. "7")
        if from_viewer == "child" and len(parts) == 1:
            if not self.child_flow_viewer.isVisible() or not self.child_scope_stack:
                QMessageBox.information(self, "Find Node", "No child scope is currently open.")
                return
            target_id = parts[0]
            found = self.child_flow_viewer.select_and_center_node(target_id)
            if not found:
                curr_prefix = self.child_scope_stack[-1][1] if self.child_scope_stack else "child"
                QMessageBox.information(self, "Find Node", f"Node '{target_id}' not found in current scope '{curr_prefix}'.")
            return

        # Case 2: Query is a single node ID from Main Scope (e.g. "328")
        if len(parts) == 1:
            target_id = parts[0]
            found = self.main_flow_viewer.select_and_center_node(target_id)
            if not found:
                QMessageBox.information(self, "Find Node", f"Node '{target_id}' not found in Main Scope (root).")
            return

        # Case 3: Hierarchical query (e.g. "328:7" or "328:210:5")
        # Step A: Find top-level root node
        root_id = parts[0]
        root_node = self.scenario.node_map.get(root_id)
        if not root_node:
            QMessageBox.information(self, "Find Node", f"Root node '{root_id}' not found.")
            return

        self.main_flow_viewer.select_and_center_node(root_id)

        # Step B: Traverse compound nodes to construct the navigation stack
        current_node = root_node
        current_prefix = f"root:{root_id}"
        new_stack = []

        for next_id in parts[1:-1]:
            if not current_node.child_actions:
                QMessageBox.information(self, "Find Node", f"Node '{current_node.id}' in '{current_prefix}' is not a compound action.")
                return
            next_node = current_node.child_id_map.get(next_id)
            if not next_node:
                QMessageBox.information(self, "Find Node", f"Node '{next_id}' not found in scope '{current_prefix}'.")
                return
            new_stack.append((current_node, current_prefix))
            current_node = next_node
            current_prefix = f"{current_prefix}:{next_id}"

        if not current_node.child_actions:
            QMessageBox.information(self, "Find Node", f"Node '{current_node.id}' in '{current_prefix}' is not a compound action.")
            return

        last_id = parts[-1]
        last_node = current_node.child_id_map.get(last_id)
        if not last_node:
            QMessageBox.information(self, "Find Node", f"Node '{last_id}' not found in scope '{current_prefix}'.")
            return

        new_stack.append((current_node, current_prefix))
        self.child_scope_stack = new_stack
        self._update_child_scope_ui()

        self.child_flow_viewer.select_and_center_node(last_id)
