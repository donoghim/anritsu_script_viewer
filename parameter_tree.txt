import xml.etree.ElementTree as ET
from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTreeWidget, QTreeWidgetItem, QGroupBox, QTextEdit, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from anritsu_parser import AnritsuNode

class ParameterTreeWidget(QWidget):
    """Widget for displaying Node Details, Parameter Tree, and Transitions/Conditions."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Header Information Panel
        self.info_box = QGroupBox("Step Details")
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(2)

        self.lbl_version = QLabel("Version: v1.0.1")
        self.lbl_file = QLabel("Current File: -")
        self.lbl_step = QLabel("Step: -")
        self.lbl_type = QLabel("Type: -")
        self.lbl_desc = QLabel("Description: -")
        self.lbl_params_title = QLabel("Parameters:")

        bold_font = QFont()
        bold_font.setBold(True)
        self.lbl_step.setFont(bold_font)

        info_layout.addWidget(self.lbl_version)
        info_layout.addWidget(self.lbl_file)
        info_layout.addWidget(self.lbl_step)
        info_layout.addWidget(self.lbl_type)
        info_layout.addWidget(self.lbl_desc)
        info_layout.addWidget(self.lbl_params_title)

        layout.addWidget(self.info_box)

        # 2. Toolbar for Tree Control
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.btn_expand = QPushButton("Expand All")
        self.btn_collapse = QPushButton("Collapse All")
        self.btn_show_sel = QPushButton("Show Selected Parameter")

        self.btn_expand.clicked.connect(self.expand_all)
        self.btn_collapse.clicked.connect(self.collapse_all)

        btn_layout.addWidget(self.btn_expand)
        btn_layout.addWidget(self.btn_collapse)
        btn_layout.addWidget(self.btn_show_sel)

        layout.addLayout(btn_layout)

        # 3. Parameter Tree View
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Key", "Value"])
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree_widget.setAlternatingRowColors(True)

        layout.addWidget(self.tree_widget, stretch=1)

        # 4. Transitions / Conditions Panel
        self.trans_box = QGroupBox("Transitions / Conditions")
        trans_layout = QVBoxLayout(self.trans_box)
        trans_layout.setContentsMargins(6, 6, 6, 6)
        self.trans_text = QTextEdit()
        self.trans_text.setReadOnly(True)
        self.trans_text.setMaximumHeight(90)
        trans_layout.addWidget(self.trans_text)

        layout.addWidget(self.trans_box)

    def set_file_info(self, filename: str):
        self.lbl_file.setText(f"Current File: {filename}")

    def display_node_info(self, node: Optional[AnritsuNode], scope_prefix: str = "root"):
        self.tree_widget.clear()
        self.trans_text.clear()

        if node is None:
            self.lbl_step.setText("Step: -")
            self.lbl_type.setText("Type: -")
            self.lbl_desc.setText("Description: -")
            return

        step_id_str = f"{scope_prefix}:{node.id}" if scope_prefix else node.id
        self.lbl_step.setText(f"Step: {step_id_str} - {node.name}")
        self.lbl_type.setText(f"Type: {node.type} ({node.action_type})")
        self.lbl_desc.setText(f"Description: {node.description if node.description else '-'}")

        # Populate Parameter Tree
        for param_elem in node.parameters:
            self._build_tree_items(param_elem, self.tree_widget.invisibleRootItem())

        # Expand all tree nodes by default when a node is selected
        self.tree_widget.expandAll()

        # Populate Transitions / Conditions
        trans_lines = []
        for outcome in node.outcomes:
            target_id = outcome['followingActionId']
            if target_id != "-1":
                trans_lines.append(f"-> {scope_prefix}:{target_id} ({outcome['name']})")
        
        if node.child_actions:
            trans_lines.append(f"[enter] -> {step_id_str}:0 (Start Sub-Scope)")

        self.trans_text.setText("\n".join(trans_lines))

    def _build_tree_items(self, elem: ET.Element, parent_item: QTreeWidgetItem):
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        
        # Format key name
        if tag_name == "parameter":
            xsi_type = ""
            for k, v in elem.attrib.items():
                if k.endswith("type"):
                    xsi_type = v.split(".")[0]
                    break
            key_str = xsi_type if xsi_type else "Parameter"
        else:
            key_str = tag_name

        item = QTreeWidgetItem([key_str, ""])

        # Add XML attributes as children (e.g. @variable_able, @default_able)
        for attr_k, attr_v in elem.attrib.items():
            attr_name = attr_k.split("}")[-1] if "}" in attr_k else attr_k
            if attr_name != "type":
                attr_item = QTreeWidgetItem([f"@{attr_name}", str(attr_v)])
                item.addChild(attr_item)

        text_content = (elem.text or "").strip()
        
        # Process children
        child_elems = list(elem)
        if child_elems:
            if text_content:
                val_item = QTreeWidgetItem(["value", text_content])
                item.addChild(val_item)
            for child in child_elems:
                self._build_tree_items(child, item)
            
            # Count values if multiple elements
            if len(child_elems) > 1 and not text_content:
                item.setText(1, f"({len(child_elems)} values)")
        else:
            item.setText(1, text_content)

        parent_item.addChild(item)

    def expand_all(self):
        self.tree_widget.expandAll()

    def collapse_all(self):
        self.tree_widget.collapseAll()
