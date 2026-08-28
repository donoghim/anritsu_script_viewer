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
  - `set_scope()`는 root와 child scope 모두에 대해 `_set_child_scope()`를 호출한다.
  - `_set_child_scope()`에서 전체 연결 관계를 분석해 계층, 레인, 좌표 및 연결 경로를 계산한다.
  - 자동 레이아웃과 XML `displayInformation` 좌표 레이아웃을 모두 지원한다.
  - `set_show_detail()`로 노드 부가 정보를 표시하거나 숨긴다.
  - `set_show_main_stream_only()`로 START에서 outcome을 따라 도달 가능한 모든 주 흐름 노드와 내부 연결선만 표시한다.
  - `node_selected`, `compound_selected` 시그널로 메인 창에 사용자 선택을 알린다.

### 전체 처리 흐름

1. `set_scope(nodes, scope_prefix)`가 scene, 노드 맵, 선택 상태와 연결선 강조 상태를 초기화한다.
2. 노드가 없으면 빈 화면으로 종료한다.
3. scope 종류와 관계없이 `_set_child_scope()`를 호출한다.
4. 현재 scope에 포함된 노드만으로 `node_map`, incoming edge, outgoing edge를 구성한다. scope 밖의 `followingActionId`는 연결선으로 처리하지 않는다.
5. 위상 정렬과 outcome 관계를 바탕으로 세로 레벨(rank), 가로 레인(lane), 각 노드의 좌표를 계산한다.
6. 노드 박스와 모든 유효 outcome 연결선을 scene에 추가하고, 계산된 도형 범위로 스크롤 가능한 scene 영역을 설정한다.
5. 노드 클릭 시 기존 선택 및 강조를 해제하고, 선택 노드와 연결된 입·출력 선을 굵게 강조한 뒤 `node_selected`를 발행한다.
6. 자식 Action이 있는 노드를 더블 클릭하면 `compound_selected`를 발행하여 메인 창이 해당 child scope를 연다.

> 참고: `set_scope()`의 `_set_child_scope()` 호출 뒤에는 `return`이 있다. 따라서 그 아래에 남아 있는 root 전용 배치 코드와 `_conn_true()`, `_conn_false()`, `_conn_timeout()`, `_conn_return()` 등의 특수 연결선 메서드는 현재 화면 렌더링 경로에서 호출되지 않는다.

### 용어 정의

| 용어 | 코드상 표현 | 의미 |
| --- | --- | --- |
| 노드 | `AnritsuNode` | 하나의 Action/Step을 나타내는 그래프의 정점이다. |
| edge | `edges` | 한 노드의 outcome이 다른 노드를 가리키는 전이 연결이다. 연결선 하나가 edge 하나에 대응한다. |
| incoming / outgoing | `incoming`, `outgoing` | 특정 노드로 들어오는 edge / 특정 노드에서 나가는 edge 목록이다. |
| START | `start_node` | 현재 scope의 흐름 시작 노드다. `action_type == "START"` 또는 ID `"0"`을 우선 사용한다. |
| primary node | `primary_node_ids` | START에서 모든 outcome을 따라 도달 가능한 전체 노드 집합이다. 결과값의 정상/비정상 구분과 무관하다. |
| START 비도달 노드 | `start_unreachable_node_ids` | 현재 scope에는 있지만 START에서 도달할 수 없는 노드 집합이다. 완전히 고립된 노드와 별도 연결 요소를 모두 포함한다. |
| START 비도달 시작 노드 | `unreachable_entry_node_ids` | START 비도달 노드 중 같은 집합 내부에 선행 edge가 없는 노드다. 독립 연결 요소의 시작점 후보이다. 순환만 있는 연결 요소는 XML 순서가 가장 빠른 노드를 대표 시작점으로 선택할 수 있다. |
| 대표 주 흐름 | `main_spine_node_ids` | START에서 선택 규칙으로 따라간 단일 대표 경로다. 이 경로의 노드는 lane 0에 배치된다. |
| rank | `rank` | 노드의 세로 순서(Y축 레벨)다. rank가 작을수록 위, 클수록 아래에 배치된다. |
| lane | `lane_by_id` | 노드가 배치되는 세로 열(X축 컬럼) 번호다. lane 0은 대표 주 흐름이고, lane 1 이상은 분기 또는 START 비도달 흐름에 사용한다. |
| 포트 | 포트 오프셋 | 노드 박스에서 edge가 출발하거나 도착하는 접속 지점이다. 여러 edge가 겹치지 않도록 10px 단위로 분리한다. |
| 트랙 | `track_x` | 노드 박스를 피하기 위해 edge가 수직으로 이동하는 연결선 통로의 X 좌표다. 열 사이 또는 그래프 외곽에 배치된다. |
| 직접 분기 노드 | `direct_primary_branch_ids` | 대표 주 흐름 노드에서 바로 나가는 edge의 목적지이며, 대표 주 흐름에 속하지 않는 노드다. 결과값과 무관하게 가까운 보조 lane부터 배치한다. |
| 결정적 부모 | `tree_parent` | 다중 incoming edge가 있는 노드에 대해 rank와 lane 계산용으로 하나만 선택한 부모 노드다. 선택되지 않은 incoming edge도 연결선으로 계속 렌더링한다. |

### 배치 조건

- 시작 노드는 `action_type == "START"` 또는 ID가 `"0"`인 노드를 우선하며, 없으면 목록의 첫 노드를 사용한다.
- 위상 정렬은 incoming edge가 없는 노드부터 시작한다. 순환 참조로 처리되지 않은 노드는 마지막에 추가 레벨을 부여한다.
- 정상 결과는 `NORMAL_LABELS`에 등록된 값이다. 예: `OK`, `Assigned`, `Logged`, `Displayed`, `True`, `Response Received`, `TimerStarted`, `TimerExpired`, `TimerStopped`, 인증/보안 완료, 빈 문자열. 그 외 결과는 예외 결과로 취급한다.
- `primary_node_ids`는 START에서 모든 outcome을 따라 도달 가능한 전체 노드 집합이다. 정상/비정상 결과값은 이 집합 포함 여부가 아니라 색상과 라우팅 표현에만 사용한다. START에서 도달하지 못하는 나머지는 `start_unreachable_node_ids`(독립 또는 START 비도달 노드)라고 부른다.
- `main_spine_node_ids`는 START에서 Terminator 또는 `END` Action까지 이어지는 단일 대표 경로다. 결과값과 무관하게 종료점에 도달할 수 있는 후보 중 XML에서 먼저 정의된 outcome을 선택한다. 현재 spine에 이미 포함된 노드로 돌아가는 회귀 edge만 후보에서 제외하며, 순환 구조에 속하더라도 아직 방문하지 않은 경유 노드는 사용할 수 있다.
- `main_spine_node_ids`의 노드는 lane 0에 고정하고, 대표 경로 edge는 연속된 세로 레벨에 배치한다.
- 나머지 노드는 유효 incoming edge 중 하나를 결정적 부모로 선택한다. 주 흐름 edge가 우선이고, 그 외에는 정상 edge와 원래 노드/outcome 순서가 우선이다.
- 주 흐름에서 직접 분기된 모든 노드는 outcome 결과값과 무관하게 다른 보조 흐름보다 먼저 lane을 배정받고 lane 1부터 사용한다. lane 재정렬과 표시 열 재사용 이후에도 첫 번째 직접 분기 lane은 첫 번째 보조 열로 고정된다. 같은 레벨에 여러 직접 분기가 있으면 노드 겹침을 피하기 위해 두 번째 이후 직접 분기를 오른쪽 다음 빈 lane에 배치한다.
- 주 흐름 밖 노드는 결과값과 무관하게 첫 번째 유효 outcome으로 결정적 부모와 연결되면 부모 lane을 유지한다. 해당 흐름의 두 번째 이후 outcome은 새 lane으로 이동한다.
- 주 흐름과 직접 분기 노드, 그리고 각 직접 분기의 첫 번째 outcome으로 이어지는 연속 노드는 먼저 lane을 확정하고 잠근다. 이후 독립 노드와 나머지 연결 요소를 배치하며, 전역 lane 재정렬 또는 표시 열 재사용 후에도 잠긴 lane은 변경하지 않는다.
- lane 할당은 대표 주 흐름, 직접 분기, 그 외 START 도달 노드(`primary_node_ids`), START 비도달 노드(`start_unreachable_node_ids`) 순서로 수행한다. 논리 lane 배정 직후 primary 노드 전체의 lane을 저장하고, 5단계의 lane 재정렬·표시 열 재사용 후 다시 복원한다. 그 뒤 primary 노드의 최댓값 다음 lane부터 START 비도달 노드 lane을 다시 매긴다. 따라서 최종 lane 확정 과정은 primary 노드의 열을 변경하지 않으며, START 비도달 노드는 primary 노드의 좌측 배치 영역을 침범하지 않는다.
- 독립 진입 노드는 lane 2부터 배정한다. 표시 열 재사용 시에도 lane 1은 재사용하지 않으므로 주 흐름 직접 분기용 열을 차지할 수 없다.
- 시작 노드가 아니고 incoming edge가 없지만 현재 scope 안의 outgoing edge가 있는 독립 진입 노드는, 직접 연결되는 목적지 중 가장 이른 레벨의 바로 위 레벨로 이동한다. 최상단 새 열에 고정하는 대신 목적지 근처에 배치해 연결선을 짧게 유지한다.
- 연결 수가 많은 보조 lane은 왼쪽에 오도록 lane을 다시 정렬한다. 서로 세로 범위가 겹치지 않는 lane은 같은 표시 열을 재사용한다.
- lane 0과 lane 1의 가로 간격은 40px로 고정한다. 연결선 수에 따른 가로 여유는 lane 1 이후의 열 간격에만 추가한다. 직선 트리 edge 이외의 연결선이 많은 레벨 간격도 세로로 넓힌다.
- `Use displayInformation Layout`이 활성화되고 노드에 원본 좌표가 있으면 그 X/Y 좌표를 우선한다. 박스가 겹치면 오른쪽으로 이동해 겹침을 해소한다.

### 연결선 연결 조건

- 모든 유효 edge는 목적지 노드 순서, 출발/목적지의 가로 거리, source/outcome 순서로 정렬한 뒤 그린다.
- 출발지와 목적지가 거의 같은 열에 있고, 목적지가 아래에 있으며, 두 노드 사이의 세로 통로를 다른 노드가 막지 않으면 수직 직선으로 연결한다.
- 그 외 edge는 출발지 하단 포트에서 나온 뒤, 가로 트랙, 세로 트랙, 목적지 직전 수평 접근선, 목적지 상단 포트를 순서대로 지나는 직교 경로로 연결한다.
- 원본 좌표 모드에서 출발지 바로 아래의 수직 통로가 비어 있으면, 목적지 바로 위에서 한 번만 꺾는 짧은 경로를 우선 사용한다.
- 일반 자동 레이아웃에서는 출발지와 목적지 열 사이의 내부 트랙을 먼저 찾는다. 사용 가능한 내부 트랙이 없으면 목적지의 좌측 또는 우측 외곽 트랙을 대체 경로로 사용한다.
- 수직 트랙은 노드 박스와 충돌하거나 이미 예약된 높이 범위와 겹치면 사용할 수 없다.
- 한 노드에 여러 edge가 있으면 10px 단위의 포트 오프셋을 부여한다. 목적지로 들어가는 수평 접근선도 기존 선과 겹치면 5px씩 위로 이동한다.
- 정상 결과는 녹색(`COL_NORMAL`), 그 외 결과는 빨간색(`COL_EXCEP`)으로 표시한다. 현재 범용 렌더러는 결과별 별도 경로 대신 이 색상 분류를 사용한다.
- 모든 연결선은 수평·수직 세그먼트, 화살표, outcome 라벨로 구성한다.
- 선택한 노드의 들어오는 선과 나가는 선은 원래 색상을 밝고 굵게 표시한다.
- `No show Main stream` 토글을 켜면 전체 연결 맵에서 START 도달 노드를 먼저 식별한 뒤, 그 노드와 내부 edge만으로 rank, lane, 열 간격, 트랙, 좌표를 처음부터 다시 계산한다. 따라서 주 흐름에서 분기된 `True`/`False` 등 모든 후속 경로가 포함되며, START 비도달 노드와 edge가 primary 노드의 배치 및 연결선 길이에 영향을 주지 않는다.

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