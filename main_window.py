import os
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QFileDialog, QPushButton, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from anritsu_parser import parse_anritsu_test_file, AnritsuScenario, AnritsuNode
from flowchart_viewer import FlowchartViewer
from parameter_tree import ParameterTreeWidget

class AnritsuScenarioViewerWindow(QMainWindow):
    """Main Window for Anritsu STD Scenario Viewer v1.0.1 with Nested Child Scope Navigation."""
    def __init__(self, default_file: Optional[str] = None):
        super().__init__()
        self.scenario: Optional[AnritsuScenario] = None
        self.current_selected_node: Optional[AnritsuNode] = None
        self.current_scope_prefix = "root"
        
        # Navigation Stack for Child Scopes: List of (node, scope_prefix)
        self.child_scope_stack: List[Tuple[AnritsuNode, str]] = []

        self.setWindowTitle("Anritsu STD Scenario Viewer v1.0.1")
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
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)

        # Left Vertical Splitter (Upper: Main Scope, Lower: Child Scope)
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
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
        if node.child_actions:
            scope_prefix = f"root:{node.id}"
            # Reset stack to level 1
            self.child_scope_stack = [(node, scope_prefix)]
            
            self._update_child_scope_ui()

    def _on_child_compound_selected(self, node: AnritsuNode):
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

        # Adjust vertical splitter
        self.left_splitter.setSizes([450, 450])

        # Enforce horizontal splitter ratio (Left: 60%, Right: 40%)
        total_w = self.main_splitter.width()
        if total_w > 700:
            self.main_splitter.setSizes([int(total_w * 0.6), int(total_w * 0.4)])

    def _on_child_node_selected(self, node: AnritsuNode):
        self.current_selected_node = node
        scope_prefix = self.child_flow_viewer.current_scope_prefix
        self.param_tree.display_node_info(node, scope_prefix=scope_prefix)

    def _on_close_or_back_child_scope(self):
        if len(self.child_scope_stack) > 1:
            # Pop nested scope and return to parent child scope
            self.child_scope_stack.pop()
            self._update_child_scope_ui()
        else:
            # Close child scope completely
            self.child_scope_stack.clear()
            self._close_child_scope()

    def _close_child_scope(self):
        self.child_flow_viewer.title_str = "Child Scope: (None)"
        self.child_flow_viewer.set_scope([], scope_prefix="")
        self.child_flow_viewer.setVisible(False)

        total_w = self.main_splitter.width()
        if total_w > 700:
            self.main_splitter.setSizes([int(total_w * 0.6), int(total_w * 0.4)])
