"""Start a real Tk GUI and a fake engine to verify run-folder archiving without API calls."""
import tempfile, time, json, sys
from pathlib import Path
import shift_corpus_gui as gui
from shift_corpus_gui import App

with tempfile.TemporaryDirectory() as td:
    base=Path(td)
    fake=base/'fake_engine.py'
    fake.write_text('''import sys, pathlib, json
args = sys.argv
out = pathlib.Path(args[args.index("--out") + 1])
print("period 2022-05-01_2022-10-27 2022-05-01..2022-10-27", flush=True)
print("sample 2022-05-01_2022-10-27 seed=1 days=180 target=180", flush=True)
(out / "query.json").write_text(json.dumps({"ok": True}))
print("wrote 1 texts", flush=True)
''')
    gui.ENGINE=fake
    original_command = gui.make_command
    gui.make_command = lambda values: original_command(values, engine=fake)
    app=App(); app.update()
    app.vars['out'].set(str(base / 'outputs'))
    app._start()
    deadline=time.monotonic()+7
    while app.proc is not None and time.monotonic()<deadline:
        app.update();time.sleep(.05)
    app.update()
    folder=app.last_run_dir
    assert folder and folder.exists(), 'Folder not created'
    manifest=json.loads((folder/'run_manifest.json').read_text())
    assert manifest['status']=='completed', manifest
    assert (folder/'collection.log').exists()
    assert (folder/'query.json').exists()
    assert 'wrote 1 texts' in (folder/'collection.log').read_text()
    # same parameters, another run must create new folder, not overwrite the previous
    app._start()
    deadline=time.monotonic()+7
    while app.proc is not None and time.monotonic()<deadline:
        app.update();time.sleep(.05)
    app.update()
    second=app.last_run_dir
    assert folder!=second and folder.exists() and second.exists()
    app.language_choice.set('English');app._set_language();app.update()
    assert 'v1.1.0' in app.title()
    app.destroy()
print('GUI start -> fake engine -> manifest/log -> new unique folder -> language switch OK')
