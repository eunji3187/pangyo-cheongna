"""
00_config.py를 importlib으로 로드해 반환하는 헬퍼.
파이썬은 숫자로 시작하는 모듈을 직접 import할 수 없으므로 이 파일을 경유한다.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "config",
    Path(__file__).parent / "00_config.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def cfg():
    return _mod
