# Revive Chess

로컬에서 실행되는 HTML 기반 체스 변형 게임입니다. 기본 체스 이동 위에, 말을 잡아 포인트를 얻고 잡힌 아군 말을 킹 앞 한 칸에 되살리는 규칙을 추가했습니다.

## 기능

- 상대 선택: `USER`(로컬 2인) 또는 `COMPUTER`(로컬 AI)를 게임 시작 전/중 선택할 수 있습니다.
- 오프라인 AI: `chess_variant/ai_data.json`에 저장된 물질 가치, 위치 평가표, 오프닝 선호도, 부활 정책 데이터를 사용해 네트워크 없이 수를 고릅니다.
- COMPUTER 난이도: `초급자`(무작위 수), `중급자`(1수 평가+약간의 흔들림), `상급자`(미니맥스 탐색)를 선택할 수 있습니다.
- 고급 체스 규칙: 캐슬링, 앙파상, 50수 규칙 무승부, 3회 반복 무승부를 지원하며 COMPUTER도 합법수 목록에 포함된 캐슬링/앙파상을 사용할 수 있습니다.
- 포인트 규칙:
  - 폰: 잡을 때 1점 / 부활 비용 2점
  - 나이트: 잡을 때 3점 / 부활 비용 6점
  - 비숍, 룩: 잡을 때 5점 / 부활 비용 10점
  - 퀸은 부활할 수 없습니다.
- 부활 횟수 제한:
  - 폰 2회
  - 나이트 1회
  - 비숍과 룩을 합쳐 총 1회
- 부활 위치: 부활한 말은 아군 킹이 상대를 바라보는 방향의 바로 앞 1칸에 생성됩니다. 해당 칸이 비어 있고 부활 후에도 자기 킹이 체크 상태가 아니어야 합니다. 체크를 당한 상태에서는 부활 기능을 사용할 수 없습니다.

## HTML 로컬 실행

브라우저에서 `web/index.html` 파일을 직접 열면 게임이 실행됩니다. `web/ai-data.js`가 AI 평가 데이터를 로컬 파일로 제공하므로 인터넷 연결이나 외부 서버가 필요 없습니다.

```bash
python -m webbrowser web/index.html
```

기존 Python/Tkinter 실행도 유지되어 개발 환경에서는 `python main.py`로 데스크톱 UI를 확인할 수 있습니다.

## Windows EXE 만들기

Windows PC에서 Python/Tkinter 버전 EXE가 필요하면 다음 명령을 실행해 `dist/ReviveChess.exe`를 생성할 수 있습니다. `ai_data.json`은 EXE 내부 번들 경로에서도 읽히도록 처리되어 EXE를 더블클릭해 바로 실행할 수 있습니다.

```bash
python -m pip install pyinstaller
pyinstaller packaging/ReviveChess.spec
```

Linux/macOS에서 PyInstaller를 실행하면 해당 OS용 실행 파일이 만들어집니다. Windows `.exe`는 Windows에서 빌드하세요.

## 테스트

```bash
python -m pytest
```
