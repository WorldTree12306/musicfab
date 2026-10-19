# 文件格式兼容路线

| 格式 | 方向 | 开源实现 | 说明 |
|---|---|---|---|
| MIDI (.mid) | 读写 | mido / pretty_midi | 完整 |
| MusicXML (.musicxml/.mxl) | 读写 | music21 / partitura | 完整 |
| MEI | 读写 | Verovio | Phase 4 |
| Guitar Pro (.gp3/.gp4/.gp5/.gpx) | 读 | PyGuitarPro | Phase 4；写可用 alphaTab/TuxGuitar 另存 |
| `.asdt`（AnthemScore 工程） | 读 | 无开源实现 | 不逆向其算法；如需要可自行导出 MIDI/MusicXML |
| Melodyne `.mdd` | 读 | 无开源实现 | 通过导出 MIDI 交互 |
| Capella `.capx` | 读 | MuseScore 部分可导入 | Phase 4 走 MuseScore |
| 音频 (.wav/.flac/.ogg/.mp3) | 读 | soundfile / ffmpeg | mp3 需 ffmpeg 或 libsndfile>=1.2 |

## 边界说明
本项目坚持 clean-room：与商业软件只做**用户自有文件的格式互操作**，不反编译其算法、不提取其模型权重、不绕过其授权。
