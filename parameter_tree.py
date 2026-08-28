import xml.etree.ElementTree as ET
import json
from pathlib import Path
from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTreeWidget, QTreeWidgetItem, QGroupBox, QTextEdit, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from anritsu_parser import AnritsuNode
from version import VERSION

class ParameterTreeWidget(QWidget):
    """Widget for displaying Node Details, Parameter Tree, and Transitions/Conditions."""
    display_layout_toggled = pyqtSignal(bool)
    detail_toggled = pyqtSignal(bool)
    TEXT_STYLE_CONFIG_PATH = Path(__file__).with_name("parameter_tree.config")
    TEXT_STYLES = {
        "muted": {"foreground": "#9A9A9A", "italic": True},
        "emphasis": {"foreground": "#7A5700", "background": "#FFF3CD", "bold": True},
        "highlight": {"foreground": "#003B73", "background": "#DCEEFF", "bold": True},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_style_rules = self._load_text_style_rules()
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

        self.lbl_version = QLabel(f"Version: v{VERSION}")
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
        self.btn_show_sel = QPushButton("Use displayInformation Layout")
        self.btn_show_sel.setCheckable(True)
        self.btn_show_sel.setToolTip("Render action boxes using the scenario displayInformation coordinates")
        self.btn_show_detail = QPushButton("Show Detail")
        self.btn_show_detail.setCheckable(True)
        self.btn_show_detail.setChecked(True)
        self.btn_show_detail.setToolTip("Show or hide second-line box details")

        self.btn_expand.clicked.connect(self.expand_all)
        self.btn_collapse.clicked.connect(self.collapse_all)
        self.btn_show_sel.toggled.connect(self.display_layout_toggled)
        self.btn_show_detail.toggled.connect(self.detail_toggled)

        btn_layout.addWidget(self.btn_expand)
        btn_layout.addWidget(self.btn_collapse)
        btn_layout.addWidget(self.btn_show_sel)
        btn_layout.addWidget(self.btn_show_detail)

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
        self._apply_text_style(item, key_str)

        # Add XML attributes as children (e.g. @variable_able, @default_able)
        for attr_k, attr_v in elem.attrib.items():
            attr_name = attr_k.split("}")[-1] if "}" in attr_k else attr_k
            if attr_name != "type":
                attr_item = QTreeWidgetItem([f"@{attr_name}", str(attr_v)])
                self._apply_text_style(attr_item, attr_name)
                self._apply_text_style(attr_item, str(attr_v))
                item.addChild(attr_item)

        text_content = (elem.text or "").strip()
        
        # Process children
        child_elems = list(elem)
        if child_elems:
            if text_content:
                val_item = QTreeWidgetItem(["value", text_content])
                self._apply_text_style(val_item, text_content)
                item.addChild(val_item)
            for child in child_elems:
                self._build_tree_items(child, item)
            
            # Count values if multiple elements
            if len(child_elems) > 1 and not text_content:
                item.setText(1, f"({len(child_elems)} values)")
        else:
            item.setText(1, text_content)
            self._apply_text_style(item, text_content)

        parent_item.addChild(item)

    def _load_text_style_rules(self) -> List[Dict[str, str]]:
        try:
            with self.TEXT_STYLE_CONFIG_PATH.open(encoding="utf-8") as config_file:
                config = json.load(config_file)
        except (OSError, json.JSONDecodeError):
            return []

        rules = config.get("rules", [])
        return [
            rule for rule in rules
            if isinstance(rule, dict)
            and isinstance(rule.get("text"), str)
            and rule.get("match", "exact") in {"exact", "contains"}
            and rule.get("style") in self.TEXT_STYLES
        ]

    def _apply_text_style(self, item: QTreeWidgetItem, text: str):
        comparison_text = text.casefold()
        for rule in self.text_style_rules:
            target_text = rule["text"].casefold()
            matches = (
                comparison_text == target_text
                if rule.get("match", "exact") == "exact"
                else target_text in comparison_text
            )
            if not matches:
                continue

            style = self.TEXT_STYLES[rule["style"]]
            font = item.font(0)
            font.setBold(style.get("bold", False))
            font.setItalic(style.get("italic", False))
            for column in range(2):
                item.setForeground(column, QColor(style["foreground"]))
                if "background" in style:
                    item.setBackground(column, QColor(style["background"]))
                item.setFont(column, font)
            return

    def expand_all(self):
        self.tree_widget.expandAll()

    def collapse_all(self):
        self.tree_widget.collapseAll()
