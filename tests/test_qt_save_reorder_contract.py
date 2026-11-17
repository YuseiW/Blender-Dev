"""Static and mock contract tests for Qt DnD reorder and JSON overwrite save.

No Blender or PySide6 installation is necessary for these logic tests.
Run after apply_save_reorder.py in the repo root:
    python tests/test_qt_save_reorder_contract.py
"""
import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
QT = ROOT / "scripts/addons/anim_reference_tool/qt_manager_app.py"
BRIDGE = ROOT / "scripts/addons/anim_reference_tool/operators/manager_external.py"


def extract_func(path, name, cls=None, namespace=None):
    tree = ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    nodes = tree.body
    if cls:
        matches = [x for x in nodes if isinstance(x, ast.ClassDef) and x.name == cls]
        assert len(matches) == 1
        nodes = matches[0].body
    matches = [x for x in nodes if isinstance(x, ast.FunctionDef) and x.name == name]
    assert len(matches) == 1, name
    fn = matches[0]
    mod = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    scope = dict(namespace or {})
    exec(compile(mod, str(path), "exec"), scope)
    return scope[name]


class FakeQtUI:
    def __init__(self, refs):
        self.refs = [{"uid": x} for x in refs]
        self.pending = None
        self.selected_uid = None
        self.commands = []
        self.statuses = []

    def _current_refs(self):
        return self.refs

    def _set_status(self, *msg):
        self.statuses.append(msg)

    def command(self, action, **kwargs):
        self.commands.append((action, kwargs))


def check_drag_positions():
    q_src = QT.read_text(encoding="utf8")
    assert 'MIME_REFERENCE_TYPE' in q_src
    assert 'UI1_EXPLORER_IMAGE_DROP_V1' in q_src, "Explorer importer must remain"
    ref_method = extract_func(QT, "_reorder_ref", cls="ManagerWindow")
    ids = ["A", "B", "C", "D"]
    cases = 0
    for src in range(len(ids)):
        for insertion in range(len(ids)+1):
            ui = FakeQtUI(ids)
            ref_method(ui, ids[src], insertion)
            dest = insertion - 1 if insertion > src else insertion
            if dest == src:
                assert not ui.commands
            else:
                assert ui.commands == [("reorder_reference", {
                    "index": src, "uid": ids[src], "to_index": dest
                })]
                result = ids[:]
                result.insert(dest, result.pop(src))
                assert result.index(ids[src]) == dest
            cases += 1
    print(f"PASS: Qt reference insertion slot conversion ({cases} cases)")


def check_overwrite_save():
    fn = extract_func(QT, "_save_project", cls="ManagerWindow")
    update_fn = extract_func(QT, "_editor_update_for_save", cls="ManagerWindow")
    submit_fn = extract_func(QT, "_submit_project_save", cls="ManagerWindow")

    class UI:
        def __init__(self, path):
            self.state = {"project_filepath": path}
            self.commands = []
            self.as_called = 0
            self.ref_index = -1
            self.duration = SimpleNamespace(value=lambda: 10)
            self.instruction = SimpleNamespace(toPlainText=lambda: "new note")
        def _current_refs(self):
            return [{"uid": "r1", "duration": 8, "instruction": "old note"}]
        def command(self, name, **kwargs):
            self.commands.append((name, kwargs))
        def _submit_project_save(self, path):
            submit_fn(self, path)
        def _editor_update_for_save(self):
            return update_fn(self)
        def _save_project_as(self):
            self.as_called += 1

    existing = UI("C:/studio/scene.json")
    fn(existing)
    assert existing.commands == [("save_project", {"path": "C:/studio/scene.json"})]
    assert not existing.as_called
    new = UI("")
    fn(new)
    assert new.as_called == 1 and not new.commands
    edited = UI("C:/studio/scene.json")
    edited.ref_index = 0
    fn(edited)
    assert edited.commands[0][0] == "save_project"
    ref_update = edited.commands[0][1]["ref_update"]
    assert ref_update["uid"] == "r1" and ref_update["index"] == 0
    assert ref_update["expected_instruction"] == "old note"
    assert ref_update["instruction"] == "new note" and ref_update["duration"] == 10
    print("PASS: overwrite uses stored path, Save As fallback, and captures editor edits")


def check_blender_reorder():
    class Collection(list):
        def move(self, i, j):
            self.insert(j, self.pop(i))
    def build_env():
        refs = Collection([SimpleNamespace(uid=x, duration=8, instruction="old") for x in ["A", "B", "C", "D"]])
        proj = SimpleNamespace(active_category="STORYBOARD", project_filepath="")
        scene = SimpleNamespace(name="Scene", animref_project=proj)
        cut = SimpleNamespace(refs=refs)
        def fake_save(project, path):
            project.project_filepath = path
        scope = {
            "_current_window_and_scene": lambda: (None, scene),
            "_active_cut": lambda p: cut,
            "get_reference_collection": lambda c, cat: c.refs,
            "_refresh_display": lambda s: None,
            "_snapshot": lambda: {"scene": "Scene", "project_filepath": proj.project_filepath},
            "save_project": fake_save,
        }
        return refs, proj, scope
    for src in range(4):
        for dest in range(4):
            refs, proj, scope = build_env()
            handler = extract_func(BRIDGE, "_process_request", namespace=scope)
            result = handler({"action": "reorder_reference", "args": {"index":src, "uid": "ABCD"[src], "to_index":dest}, "expect_scene":"Scene"})
            assert result["ok"] and result["state"]["scene"] == "Scene"
            assert [r.uid for r in refs][dest] == "ABCD"[src]
    refs, proj, scope = build_env()
    handler = extract_func(BRIDGE, "_process_request", namespace=scope)
    try:
        handler({"action": "reorder_reference", "args": {"index":0,"uid":"WRONG","to_index":3}, "expect_scene":"Scene"})
    except ValueError:
        pass
    else:
        raise AssertionError("Mismatched UID must reject stale request")
    assert [r.uid for r in refs] == ["A", "B", "C", "D"]
    try:
        handler({"action": "reorder_reference", "args": {"index":0,"uid":"A","to_index":10}, "expect_scene":"Scene"})
    except ValueError:
        pass
    else:
        raise AssertionError("Out-of-range destination must be rejected")
    assert [r.uid for r in refs] == ["A", "B", "C", "D"]
    print("PASS: Blender reorder + stale UID and invalid index checks")

    save_args = {
        "path":"C:/studio/project.json",
        "ref_update": {
            "index":0, "uid":"A", "expected_duration":8,
            "expected_instruction":"old", "duration":12,
            "instruction":"new note",
        },
    }
    result = handler({"action":"save_project", "args":save_args, "expect_scene":"Scene"})
    assert result["ok"] and proj.project_filepath == save_args["path"]
    assert refs[0].duration == 12 and refs[0].instruction == "new note"
    # Failed disk writes must not leave editor changes applied in Blender.
    refs, proj, scope = build_env()
    def fail_save(project,path):
        raise PermissionError("disk is read-only")
    scope["save_project"] = fail_save
    handler = extract_func(BRIDGE, "_process_request", namespace=scope)
    try:
        handler({"action":"save_project", "args":save_args, "expect_scene":"Scene"})
    except PermissionError:
        pass
    else:
        raise AssertionError("Failed disk write must be reported")
    assert refs[0].duration == 8 and refs[0].instruction == "old"
    print("PASS: Save applies editor data and rolls back on disk errors")


if __name__ == "__main__":
    check_drag_positions()
    check_overwrite_save()
    check_blender_reorder()
    print("ALL CONTRACT TESTS PASSED (no Blender/Qt runtime GUI test)")
