from scripts.apply_pwn_tft_layout import apply_layout


def test_opt_in_idempotent_and_restores_after_update(tmp_path):
    style = tmp_path / 'style.css'
    source = tmp_path / 'custom.css'
    marker = tmp_path / 'enabled'
    block = '/* RAGNAR-TFT-BEGIN */\n.face {width:100%}\n/* RAGNAR-TFT-END */\n'
    source.write_text(block)
    style.write_text('body {color:red}\n')
    assert not apply_layout(style, source, marker)
    marker.touch()
    assert apply_layout(style, source, marker)
    assert not apply_layout(style, source, marker)
    assert style.read_text().count('RAGNAR-TFT-BEGIN') == 1
    style.write_text('body {color:blue}\n')  # upstream replaces stylesheet
    assert apply_layout(style, source, marker)
    assert 'color:blue' in style.read_text() and block in style.read_text()


def test_replaces_older_marked_layout_preserving_other_css(tmp_path):
    style, source, marker = (tmp_path / n for n in ('style.css', 'new.css', 'enabled'))
    marker.touch()
    style.write_text('before{}\n/* RAGNAR-TFT-BEGIN: old */\nold{}\n/* RAGNAR-TFT-END */\nafter{}\n')
    source.write_text('/* RAGNAR-TFT-BEGIN */\nnew{}\n/* RAGNAR-TFT-END */')
    assert apply_layout(style, source, marker)
    assert 'old{}' not in style.read_text()
    assert 'before{}' in style.read_text() and 'after{}' in style.read_text()
