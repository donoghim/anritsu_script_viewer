import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any

class AnritsuNode:
    """Class representing a single Action/Step node in an Anritsu scenario file."""
    def __init__(self, node_id: str, name: str, node_type: str, action_type: str = "", 
                 description: str = "", procedure_lib: str = "", raw_element: Optional[ET.Element] = None):
        self.id = node_id
        self.name = name
        self.type = node_type  # e.g., 'controlAction', 'procedureAction', 'compoundAction'
        self.action_type = action_type  # e.g., 'START', 'ASSIGNMENT', 'Configuration', 'General'
        self.description = description
        self.procedure_lib = procedure_lib
        self.raw_element = raw_element
        self.outcomes: List[Dict[str, str]] = []  # List of {'id', 'followingActionId', 'name', 'terminatorId'}
        self.child_actions: List['AnritsuNode'] = []  # Sub-actions for compoundAction
        self.child_id_map: Dict[str, 'AnritsuNode'] = {}
        self.parameters: List[ET.Element] = []
        self.layout_info: Dict[str, Any] = {}

    def add_outcome(self, outcome_id: str, following_id: str, name: str, terminator_id: str = ""):
        self.outcomes.append({
            'id': outcome_id,
            'followingActionId': following_id,
            'name': name,
            'terminatorId': terminator_id
        })

    def __repr__(self):
        return f"<AnritsuNode id={self.id} name='{self.name}' type={self.type}>"


class AnritsuScenario:
    """Class holding the parsed scenario metadata and node hierarchy."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_version = ""
        self.rtd_version = ""
        self.catalogs: List[str] = []
        self.procedure_libraries: List[Dict[str, str]] = []
        self.root_actions: List[AnritsuNode] = []
        self.node_map: Dict[str, AnritsuNode] = {}


def parse_action_element(elem: ET.Element) -> AnritsuNode:
    """Parses a single <action> XML element into an AnritsuNode object."""
    # Extract xsi:type attribute
    xsi_type = ""
    for attr, val in elem.attrib.items():
        if attr.endswith("type"):
            xsi_type = val
            break
    
    node_id = elem.attrib.get("id", "")
    name = elem.attrib.get("name", "")
    description = elem.attrib.get("description", "")
    proc_lib = elem.attrib.get("procedureLibraryName", "")
    
    action_type = elem.attrib.get("controlActionType", "")
    if not action_type:
        action_type = elem.attrib.get("procedureActionType", "")
        
    node = AnritsuNode(
        node_id=node_id,
        name=name,
        node_type=xsi_type,
        action_type=action_type,
        description=description,
        procedure_lib=proc_lib,
        raw_element=elem
    )
    
    # Parse outcomes, parameters, and child actions
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "outcome":
            node.add_outcome(
                outcome_id=child.attrib.get("id", ""),
                following_id=child.attrib.get("followingActionId", "-1"),
                name=child.attrib.get("name", ""),
                terminator_id=child.attrib.get("terminatorId", "")
            )
        elif tag == "parameter":
            node.parameters.append(child)
        elif tag == "action":
            child_node = parse_action_element(child)
            node.child_actions.append(child_node)
            node.child_id_map[child_node.id] = child_node
            
    # Parse layout information if present
    disp_info = elem.find("./displayInformation/layoutInformation")
    if disp_info is not None:
        for a_tag in disp_info.findall("a"):
            if a_tag.attrib.get("id") == node_id:
                node.layout_info = {
                    'x': int(a_tag.attrib.get("x", 0)),
                    'y': int(a_tag.attrib.get("y", 0)),
                    'row': int(a_tag.attrib.get("row", 0))
                }
                break

    return node


def parse_anritsu_test_file(file_path: str) -> AnritsuScenario:
    """Parses an Anritsu .test XML scenario file and returns an AnritsuScenario instance."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    scenario = AnritsuScenario(file_path)
    scenario.file_version = root.attrib.get("fileVersion", "")
    scenario.rtd_version = root.attrib.get("rtdVersion", "")
    
    for child in root:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "catalog":
            if child.text:
                scenario.catalogs.append(child.text)
        elif tag == "procedureLibrary":
            scenario.procedure_libraries.append({
                'name': child.text or "",
                'version': child.attrib.get("procedureLibraryVersion", "")
            })
        elif tag == "action":
            action_node = parse_action_element(child)
            scenario.root_actions.append(action_node)
            scenario.node_map[action_node.id] = action_node
            
    return scenario


if __name__ == "__main__":
    import sys
    test_file = r"d:\work_bench\260824_Anritsu_Script\NBIoT_07.01_Tracking_area_update.test"
    scen = parse_anritsu_test_file(test_file)
    print(f"File loaded: {scen.file_path}")
    print(f"Total Root Actions: {len(scen.root_actions)}")
    for act in scen.root_actions:
        print(f" - [{act.id}] {act.name} ({act.type}) -> Outcomes: {len(act.outcomes)}, Children: {len(act.child_actions)}")
        if act.child_actions:
            for ca in act.child_actions:
                print(f"     └─ [{ca.id}] {ca.name} ({ca.type})")
