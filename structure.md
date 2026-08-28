# Python 모듈 기능 명세

## 전체 구조

이 애플리케이션은 Anritsu `.test` XML 시나리오를 읽어 Action 흐름을 그래프로 시각화하고, 선택한 Action의 상세 파라미터를 표시하는 PyQt6 데스크톱 뷰어이다.

```text
app.py
  -> main_window.py
       -> anritsu_parser.py
       -> flowchart_viewer.py
       -> parameter_tree.py
       -> version.py
```

## `app.py`

### 역할

- 애플리케이션 실행 진입점이다.
- `QApplication`을 생성하고 Fusion 스타일을 적용한다.
- 첫 번째 명령행 인자가 존재하는 파일 경로이면 기본 시나리오 파일로 전달한다.
- `AnritsuScenarioViewerWindow`를 표시하고 Qt 이벤트 루프를 시작한다.

### 주요 인터페이스

- `main()`: Qt 애플리케이션과 메인 창을 초기화하고 실행한다.

## `anritsu_parser.py`

### 역할

- Anritsu `.test` XML 파일을 애플리케이션에서 사용할 시나리오 객체 트리로 변환한다.
- 최상위 Action과 compoundAction 내부의 하위 Action을 재귀적으로 파싱한다.
- Action 전이(outcome), 파라미터 XML, 라이브러리 정보 및 `displayInformation` 좌표를 보존한다.

### 주요 데이터 모델

- `AnritsuNode`
  - 하나의 Action/Step을 표현한다.
  - ID, 이름, XML 타입, 제어/프로시저 Action 타입, 설명, 프로시저 라이브러리 이름을 보관한다.
  - `outcomes`에 다음 Action ID와 전이 이름을 저장한다.
  - `child_actions`와 `child_id_map`으로 compoundAction의 하위 범위를 표현한다.
  - `parameters`에 원본 parameter XML 요소를 저장한다.
  - `layout_info`에 원본 레이아웃의 X/Y/행 정보를 저장한다.

- `AnritsuScenario`
  - 파일 경로와 파일/RTD 버전, catalog, procedure library 목록을 보관한다.
  - `root_actions`에 최상위 Action을, `node_map`에 최상위 ID별 Action을 저장한다.

### 주요 인터페이스

- `parse_action_element(elem)`: XML `<action>` 요소 하나를 `AnritsuNode`로 변환하고 outcome, parameter, 자식 Action 및 레이아웃 정보를 채운다.
- `parse_anritsu_test_file(file_path)`: XML 파일을 읽어 `AnritsuScenario`를 반환한다.

## `flowchart_viewer.py`

### 역할

- `AnritsuNode` 목록을 QGraphicsScene 기반 흐름도로 렌더링한다.
- Action의 종류와 이름에 따라 노드 색상 및 테두리를 구분한다.
- 정상, 조건 분기, 오류/시간 초과, 되돌아가는 전이를 직교 연결선과 화살표로 표현한다.
- 클릭한 노드의 연결선을 강조하고, compoundAction 더블 클릭 시 하위 scope 진입 이벤트를 발행한다.

### 주요 구성 요소

- `GraphicsNodeItem`
  - 하나의 Action을 사각형 노드로 표시한다.
  - Action 타입에 따라 시작, 프로시저, compound, 종료, 대기/타이머, 조건 분기 등의 스타일을 적용한다.
  - 상세 표시가 활성화되면 timeout, duration, display name, 조건식을 두 번째 줄에 표시한다.
  - 클릭/더블 클릭을 `FlowchartViewer`에 전달한다.

- `CustomGraphicsView`
  - 일반 마우스 휠은 스크롤로 처리한다.
  - Ctrl+마우스 휠은 마우스 위치 기준 확대/축소로 처리한다.

- `FlowchartViewer`
  - 그래프 씬, 뷰, 제목 및 scope 닫기/선택 노드 중앙 배치 버튼을 관리한다.
  - `set_scope()`로 현재 scope의 노드를 초기화하고, root와 child scope에 맞는 렌더링 경로를 선택한다.
  - root scope는 `set_scope()` 내부의 전용 스트림/예외 열 배치와 특수 연결선 규칙으로 렌더링한다.
  - child scope는 `_set_child_scope()`에서 전체 연결 관계를 분석해 계층, 레인, 좌표 및 연결 경로를 계산한다.
  - 자동 레이아웃과 XML `displayInformation` 좌표 레이아웃을 모두 지원한다.
  - `set_show_detail()`로 노드 부가 정보를 표시하거나 숨긴다.
  - `node_selected`, `compound_selected` 시그널로 메인 창에 사용자 선택을 알린다.

### 전체 처리 흐름

1. `set_scope(nodes, scope_prefix)`가 scene, 노드 맵, 선택 상태와 연결선 강조 상태를 초기화한다.
2. 노드가 없으면 빈 화면으로 종료한다.
3. `scope_prefix == "root"`이면 root 전용 레이아웃을 수행하고, 그 외 하위 scope는 `_set_child_scope()`를 호출한다.
4. 노드 박스와 모든 유효 outcome 연결선을 scene에 추가하고, 계산된 도형 범위로 스크롤 가능한 scene 영역을 설정한다.
5. 노드 클릭 시 기존 선택 및 강조를 해제하고, 선택 노드와 연결된 입·출력 선을 굵게 강조한 뒤 `node_selected`를 발행한다.
6. 자식 Action이 있는 노드를 더블 클릭하면 `compound_selected`를 발행하여 메인 창이 해당 child scope를 연다.

### 배치 조건

#### 공통

- 현재 scope에 포함된 노드 ID를 목적지로 가지는 outcome만 화면 연결선으로 처리한다.
- 시작 노드는 `action_type == "START"` 또는 ID가 `"0"`인 노드를 우선하며, 없으면 목록의 첫 노드를 사용한다.
- 정상 결과는 `OK`, `Assigned`, `Logged`, `Displayed`, `True`, `Response Received`, `TimerStarted`, `TimerExpired`, `TimerStopped`, 인증/보안 완료, 빈 문자열 등 `NORMAL_LABELS`에 등록된 값이다.
- `Timeout`, `False`, `Fail`, `Failed`, `Error`, `System Error`는 예외 결과로 분류한다.

#### Root scope

- 모든 유효 outcome을 대상으로 위상 정렬을 수행해 일반 연결이 위에서 아래로 흐르도록 노드 순서를 결정한다.
- 순환 참조로 위상 정렬되지 않은 노드는 마지막에 추가하고 복귀 연결선으로 처리한다.
- 시작 노드에서 첫 번째 정상 outcome을 계속 따라간 노드 집합을 주 흐름으로 지정하고 좌측 첫 번째 열에 배치한다.
- 주 흐름 이외의 연결된 노드는 보조 stream lane에 배치한다. 동일 연결 요소는 인접하게 배치하며, 보조 stream의 정상 후속 노드는 같은 lane을 유지한다.
- 예외 결과로만 도달하는 노드는 우측 예외 열 후보가 된다. 정상 결과로도 도달하는 노드는 예외 결과가 있어도 정상 열을 우선한다.

#### Child scope

- 전체 edge map을 만든 뒤 위상 레벨을 계산한다. 목적지는 원칙적으로 출발지보다 아래 레벨에 배치한다.
- 시작점에서 정상 outcome 또는 `Timeout` outcome 중 후속 경로가 가장 긴 edge를 골라 주 세로 흐름으로 만든다. 길이가 같으면 정상 outcome을 우선한다.
- 주 흐름은 lane 0에 연속 배치한다. 그 외 노드는 선택된 정상 부모와 연결되면 부모 lane을 유지하고, 분기 노드는 별도 lane에 배치한다.
- 노드가 동시에 존재하는 세로 구간이 겹치지 않으면 종료된 lane을 다른 흐름에서 재사용한다.
- `Use displayInformation Layout`이 활성화되고 XML 좌표가 있으면 해당 좌표를 우선하며, 겹치는 박스는 오른쪽으로 이동해 겹침을 해소한다.

### 연결선 연결 조건

#### Root scope 특수 연결선

- 같은 열에서 목적지가 아래에 있고 중간 노드가 없으면 정상 결과를 녹색 수직 직선으로 연결한다.
- `True`는 녹색으로 노드 왼쪽의 고유 트랙을 경유한다.
- `False`, `Fail`, `Failed`, `Error`, `System Error`는 빨간색으로 노드 오른쪽의 고유 트랙을 경유한다.
- `Timeout`은 빨간색으로 오른쪽 고유 트랙을 경유하되, False/Fail과 다른 높이에서 출발한다.
- 목적지가 출발 노드와 같은 높이 또는 위에 있거나, 더 왼쪽 열에 있으면 파란색 외곽 복귀 버스를 이용한다.
- 정상 결과가 더 오른쪽 보조 lane으로 향하거나 같은 lane의 중간 노드를 건너뛰면 녹색 직교 분기선으로 연결한다.

#### Child scope 범용 연결선

- 같은 열에 있고 목적지가 아래에 있으며 경로 중간이 비어 있으면 직선 수직 연결선을 사용한다.
- 그 외 edge는 출발 포트, 수직 트랙, 목적지 직전 수평 접근선, 목적지 포트를 순서대로 갖는 직교 경로를 사용한다.
- `displayInformation` 레이아웃에서는 출발지 아래의 수직 통로가 비어 있으면 먼저 짧은 수직 하강 경로를 시도한다.
- 정상 결과는 녹색, 그 외 결과는 빨간색으로 표시한다.

#### 충돌 회피와 상호작용

- 한 노드에 여러 선이 연결되면 포트 오프셋을 다르게 하여 시작점과 도착점을 분리한다.
- 수직 트랙은 다른 선이 이미 사용하는 동일 높이 구간을 피한다.
- 목적지로의 수평 접근선은 기존 접근선과 겹치면 높이를 위로 조정한다.
- 모든 연결선은 수평과 수직 세그먼트만 사용하며, 화살표와 outcome 라벨을 함께 표시한다.
- 선택한 노드의 들어오는 선과 나가는 선은 원래 색상을 밝고 굵게 표시한다.

## `main_window.py`

### 역할

- 애플리케이션의 최상위 창과 모듈 간 이벤트 흐름을 관리한다.
- 파일 열기, 최상위 흐름도, 하위 scope 흐름도 및 파라미터 검사기를 하나의 화면에 배치한다.
- compoundAction의 중첩 scope 탐색 이력을 스택으로 관리한다.

### 화면 구성

- 상단: 시나리오 파일 열기 버튼과 현재 파일 경로 표시 영역.
- 좌측: 최상위 scope와 선택한 하위 scope의 흐름도 영역.
- 우측: 선택한 Action의 세부 정보와 XML 파라미터를 표시하는 `ParameterTreeWidget`.

### 주요 인터페이스

- `load_scenario_file(file_path)`: 파일을 파싱하고 최상위 scope를 표시하며 기존 선택/하위 탐색 상태를 초기화한다.
- `_on_main_node_selected()` / `_on_child_node_selected()`: 선택한 노드의 정보를 우측 검사기에 표시한다.
- `_on_main_compound_selected()` / `_on_child_compound_selected()`: compoundAction 하위 scope를 열고 탐색 스택에 추가한다.
- `_on_close_or_back_child_scope()`: 하위 scope를 닫거나 부모 scope로 돌아간다.
- `_on_display_layout_toggled()`: 두 흐름도에 원본 `displayInformation` 레이아웃 적용 여부를 전달하고 다시 그린다.
- `_on_detail_toggled()`: 두 흐름도에 노드 상세 표시 여부를 전달하고 다시 그린다.

## `parameter_tree.py`

### 역할

- 현재 선택된 Action의 기본 정보, XML 파라미터 구조, 전이 정보를 표시하는 우측 검사기 위젯이다.
- 흐름도 레이아웃과 노드 상세 표시 옵션을 사용자 조작으로 제어하는 시그널을 제공한다.

### 화면 구성

- Step Details: 애플리케이션 버전, 파일명, scope를 포함한 Step ID, 타입, 설명을 표시한다.
- 제어 막대: 파라미터 트리 전체 펼치기/접기, 원본 레이아웃 사용, 노드 상세 표시 전환을 제공한다.
- Parameter Tree: parameter XML의 태그, 속성 및 텍스트 값을 계층형 트리로 표시한다.
- Transitions / Conditions: 현재 노드의 다음 Action 전이와 하위 scope 시작 지점을 표시한다.

### 주요 인터페이스

- `set_file_info(filename)`: 현재 파일명을 갱신한다.
- `display_node_info(node, scope_prefix)`: 선택 노드의 정보, 파라미터 트리 및 전이를 표시한다.
- `_build_tree_items(elem, parent_item)`: XML 요소와 속성을 재귀적으로 트리 항목으로 변환한다.
- `display_layout_toggled`: 원본 레이아웃 사용 여부를 전달하는 시그널이다.
- `detail_toggled`: 노드 상세 정보 표시 여부를 전달하는 시그널이다.

## `version.py`

### 역할

- 애플리케이션 이름과 버전을 한 곳에서 관리하는 메타데이터 모듈이다.

### 제공 상수

- `APP_NAME`: 창 제목에 사용하는 애플리케이션 이름.
- `VERSION`: 창 제목과 Step Details에 표시하는 버전 문자열.