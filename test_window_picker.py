from shift_corpus_gui import App, build_window_options, make_command
from shift_corpus_engine import period_windows, parse_args
s=build_window_options('2022-05-01','2026-11-20',180,180,'proportional')
assert [w['id'] for w in s]==[w[0] for w in period_windows('2022-05-01','2026-11-20',180)]
assert len(s)==10 and s[0]['id']=='2022-05-01_2022-10-27'
assert s[-1]['id']=='2026-10-07_2026-11-20' and s[-1]['days']==45 and s[-1]['target']==45
assert build_window_options('2022-05-01','2022-05-01',180,180,'proportional')[0]['target']==1
assert build_window_options('2022-05-01','2022-05-01',180,180,'full')[0]['target']==180
app=App(); app.update()
assert len(app.window_combo['values'])==11
app.window_choice.set(app.window_combo['values'][2]); app._on_window_selected()
assert app.vars['only_period'].get()==s[1]['id']
assert s[1]['id'] in app.command_text.get('1.0','end')
assert app.summary.get().find('1 个窗口')>=0
app.vars['sample_per_period'].set('360'); app.update()
assert app.vars['only_period'].get()==s[1]['id']
app.vars['period_days'].set('30'); app.update()
assert app.vars['only_period'].get()==''
assert len(app.window_combo['values'])>50
app.vars['period_days'].set('180'); app.update()
app.window_choice.set(app.window_combo['values'][-1]); app._on_window_selected()
assert app.vars['only_period'].get()==s[-1]['id']
assert '目标90条' in app.window_choice.get()
app.language_choice.set('English'); app._set_language(); app.update()
assert app.vars['only_period'].get()==s[-1]['id']
assert 'target 90' in app.window_choice.get()
app.vars['after'].set('not-a-date');app.update()
assert str(app.window_combo['state'])=='disabled'
app.vars['after'].set('2022-05-01');app.update()
assert app.vars['only_period'].get()==s[-1]['id']
app.destroy()
print('Window picker and bilingual UI tests passed')
