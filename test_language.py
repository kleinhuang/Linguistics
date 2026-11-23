"""Headless GUI test. Use xvfb-run on Linux; macOS can run the application normally."""
from shift_corpus_gui import App, I18N, UA
assert set(I18N['zh']) == set(I18N['en']), (set(I18N['zh']) ^ set(I18N['en']))
a=App()
a.update()
assert a.language.get() == 'zh'
a.vars['sample_per_period'].set('360')
a._log('test log sample kept=1')
a._set_language() # same language; still tests rebuild
assert a.vars['sample_per_period'].get() == '360'
a.language_choice.set('English')
a._set_language()
a.update()
assert a.language.get()=='en'
assert 'English' not in a.title() or 'Corpus' in a.title()
assert 'Start collection' in a.start_button.cget('text')
assert 'test log sample kept=1' in a.logs.get('1.0','end')
assert '--sample-per-period 360' in a.command_text.get('1.0','end')
a._status('failed', code=403)
a.language_choice.set('中文')
a._set_language()
a.update()
assert '403' in a.status.get()
assert '开始采集' in a.start_button.cget('text')
assert a.vars['sample_per_period'].get() == '360'
a.destroy()
print('Language toggle UI test passed')
