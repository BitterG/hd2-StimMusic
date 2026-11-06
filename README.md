# StimMusic v2.3.0 — 打针放音乐 (MDL3 + HD2 Data Hub 现代重构版)

> 本模组已按照《MDL3 模组规范》全面迁移至 **MDL3 (3.0.0-dev.21+)** 与 **HD2 Data Hub (0.3.0+)** 现代架构。纯 PUC Lua 5.1 编写，移除旧版 FFI 与硬编码内存依赖，安全稳定，跨版本免疫。

---

## 一、核心特性

1. **平滑渐入渐出（Fade In / Fade Out）**：
   - 支持独立调节「渐入时长」与「渐出时长」，告别突兀开播与生硬掐断。
   - 连续扎针智能衔接：在淡出前无缝切入后续音频，持续保持 100% 音量，绝不发生音量中途塌陷；淡出阶段补针平滑淡入拉回。
2. **毫秒级采样动态断点接续**：
   - 打针单次播放结束后，下次扎针自动从上次停止的毫秒级采样点平滑接续，整首歌连贯听完后自动从头循环。
   - 即使在游戏内菜单任意调整针剂时长，断点位置永远精准保持。
3. **多曲目实时切歌与即时预加载**：
   - 菜单内可直接在放入文件夹的歌曲中随意选择切换，0 延迟秒播，杜绝切歌掉帧与卡顿。
4. **一键转码与自动化部署**：
   - 自带转码工具，支持将任意音频一键转换为高保真 16-bit PCM WAV。
5. **适配 MDL3 dev.43 (Audio API 2) 原生硬件句柄与无级动态调音**：
   - **原生音频句柄**：支持 API 2 返回的独立正整数音频句柄（Handle），告别粗暴全局停止，实现精准单音停止（`A.halt`）。
   - **实时动态音量控制**：在菜单中拖动音量滑块或修改配置时，通过 `A.set(h, { volume = ... })` 与 `A.master()` 实时无级生效，无需等待下一段音频或打断重播。
   - **硬件级零漂移断点**：通过 `A.info(h).position` 直读底层 XAudio2 硬件真实播放进度，暂停、掉帧或切出菜单也能 100% 精准锁定断点。
   - **双轨无缝向下兼容**：自动向下兼容 MDL3 dev.21 ~ dev.33 (Audio API 1)，新旧版本即插即用。

---

## 二、安装与前置要求

1. **前置模组**：
   - **MDL3** (3.0.0-dev.21 或更高版本)
   - **HD2 Data Hub** (0.3.0 或更高版本，`HD2Data` API 1)
   *(不再依赖旧版 Bingus Shared Loader 或 HD2Runtime)*
2. **安装方法**：
   - **Arsenal 模组管理器安装（推荐）**：直接将压缩包拖入或导入 Arsenal，启用后点击 **Deploy** 部署即可。
   - **手动安装**：将 `Addon/9ba626afa44a3aa3.patch_0`（及其同名伴随文件）放入游戏安装目录的 `Helldivers 2\data\` 文件夹中（如已有 patch_0，可顺延编号为 patch_1、patch_2 等）。

---

## 三、音乐放在哪里与格式说明

### 1. 存放目录
模组优先读取 MDL 官方标准专用目录下的音乐文件：
```text
%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\
```
*(在 Windows 资源管理器地址栏直接粘贴上方路径回车即可打开，对应实际路径通常为：`C:\Users\<你的用户名>\AppData\Local\MDL\Helldivers2\StimMusic\`)*

备用与兼容路径：
- `C:\ProgramData\MDL\Helldivers2\StimMusic\` (官方非英文系统兜底目录)
- `%LOCALAPPDATA%\CowboyBingus\Helldivers2\StimMusic\` (旧版兼容路径)
- `%LOCALAPPDATA%\MDL3\StimMusic\`
- `%APPDATA%\Arrowhead\Helldivers2\StimMusic\`

### 2. 文件命名与多曲目支持
- **默认曲目**：`stim_music.wav`
- **多曲目共存**：你可以将多首不同曲目放入同一文件夹，例如：
  - `stim_music.wav`
  - `stim_music_alt.wav`
  - `yu_ai.wav`
  - `pao_mo.wav`
  - `pi_pa.wav`
- 游戏内 MDL 菜单会自动扫描并列出这些音乐文件供你选择。你也可以在 `STIM_MUSIC_CONFIG.ini` 中修改 `track = <文件名.wav>` 指定曲目。

### 3. 音频格式要求与一键转码
- **支持格式**：**标准 16-bit PCM WAV**（单声道或立体声，推荐采样率 22050Hz 或 44100Hz）。
- **一键转码工具**：
  模组压缩包中已自带 `convert_track.cmd` 和 `convert_track.ps1`。
  - **拖拽模式**：直接把歌曲文件（.mp3 / .flac / .wav / .m4s / .aac / .ogg）拖拽到 `convert_track.cmd` 图标上，自动转码为标准 16-bit PCM WAV。
  - **批量模式**：双击运行 `convert_track.cmd`，自动扫描当前目录下的音频文件并转换为兼容格式。

---

## 四、免重启实时热更新

1. **自动指纹检测机制**：
   - 当游戏处于运行状态时，模组每 2 秒会自动对音乐文件的大小与文件头指纹（Fingerprint）进行检测。
2. **免重启实时生效场景**：
   - **替换歌曲**：直接将新的 `stim_music.wav` 覆盖到文件夹中，模组检测到文件改变后自动重载，并在下一次扎针时播放新曲目。
   - **换歌配置**：在 `STIM_MUSIC_CONFIG.ini` 中修改 `track = yu_ai.wav`，保存后 2 秒内自动生效。
   - **游戏内实时切换**：按 `ESC` -> **MDL 设置** -> **打针放音乐 (Stim Music)**，在「当前音乐 (Music Track)」中切换曲目，即刻生效！

---

## 五、MDL 游戏内设置界面 (ESC 菜单)

进入游戏后按 `ESC` -> 打开 **MDL 设置** -> 点击 **打针放音乐 (Stim Music)**，即可看到全部可调选项：

| 选项名称 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| **总开关 (Enabled)** | 开关 | 开启 | 开启或关闭打针音乐功能。 |
| **音乐文件 (Music Track)** | 单选 | 自动识别 | 实时显示与切换当前生效的曲目文件。 |
| **音乐音量 (Volume %)** | 滑块 | 100% | 0 ~ 100% 独立调节打针音乐音量，不影响游戏主音量。 |
| **针剂时长 (Stim Length ms)** | 滑块 | 6000ms | 单次扎针音乐播放时长（毫秒）。调整后断点进度依然平滑接续。 |
| **渐入时长 (Fade In ms)** | 滑块 | 500ms | 音乐开始播放时的音量淡入过渡时间（0 为立即全音量）。 |
| **渐出时长 (Fade Out ms)** | 滑块 | 1500ms | 针效结束前音乐平滑淡出的过渡时间（0 为直接截断）。 |
| **最小回血量阈值 (Min Heal)** | 滑块 | 1 | 触发音乐的最小回血增量（1-50），防持续治疗误触。 |
| **自动热重载 (Hot Reload)** | 开关 | 开启 | 开启后每 2 秒检测文件改动，免重启热更新。 |

---

## 六、状态监控与排查

- **实时状态文件**：
  `%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\STIM_MUSIC_STATUS.txt`
  游戏运行时自动记录当前播放状态、生效曲目、断点位置、针剂计数、Hub 连接等。
- **运行日志文件**：
  `%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\stim_music.log`

---

# StimMusic v2.3.0 — Stim & Healing Music Player (English Guide)

> StimMusic is a lightweight, modern audio enhancement mod built for **MDL3 (3.0.0-dev.21+)** and **HD2 Data Hub (0.3.0+)**.
> Written in 100% pure PUC Lua 5.1 with zero FFI, zero memory patching, and full game patch resilience.

---

## 1. Features

1. **Smooth Fade In & Fade Out**:
   - Independently configurable fade-in and fade-out durations in milliseconds.
   - Intelligent chaining: stimming during music playback seamlessly sustains 100% volume without cutting or dipping; stimming during fade-out smoothly ramps volume back up.
2. **Sample-Accurate Resume**:
   - Stim playback resumes exactly where it left off, listening through entire songs across multiple stims before looping.
   - Adjusting stim playback duration in the in-game menu never shifts or breaks your playback position.
3. **Multi-Track Hot-Switching**:
   - Place multiple `.wav` songs in the folder; easily pick and switch tracks on the fly in the in-game ESC menu with zero stutter.
4. **Bilingual UI (English & Chinese)**:
   - Automatically detects your game / MDL client language. Displays English on English/international clients and Chinese on Chinese clients.
   - Can also be forced via `language = en` or `language = zh` in `STIM_MUSIC_CONFIG.ini`.
5. **One-Click Audio Converter Included**:
   - Includes `convert_track.cmd` and `convert_track.ps1` to convert any audio (.mp3, .flac, .ogg, .m4s, etc.) into high-fidelity 16-bit PCM WAV with one click or drag-and-drop.
6. **MDL3 dev.43 (Audio API 2) Native Handle & Dynamic Realtime Control**:
   - **Native Audio Handles**: Fully tracks individual voice handles (`h > 0`) for fine-grained per-voice stopping (`A.halt`).
   - **Live Volume Modulation**: Adjusting volume via slider immediately updates running playback via `A.set(handle, { volume = ... })` and `A.master()` without restarting or stuttering.
   - **Hardware-Accurate Zero-Drift Resume**: Queries native XAudio2 playback seconds via `A.info(handle).position` for perfect checkpoint preservation across menu pauses and framerate dips.
   - **100% Backward Compatibility**: Seamlessly runs on both MDL3 dev.43+ (API 2) and dev.21-33 (API 1).

---

## 2. Requirements & Installation

### Requirements
- **MDL3** (v3.0.0-dev.21 or later)
- **HD2 Data Hub** (v0.3.0 or later, `HD2Data` API 1)

*(Legacy loaders like Bingus Shared Loader or HD2Runtime are NOT required).*

### Installation
- **Arsenal Mod Manager (Recommended)**:
  Drag and drop `StimMusic-2.3.0.zip` into Arsenal Mod Manager, enable it, and click **Deploy**.
- **Manual Installation**:
  Extract `Addon/9ba626afa44a3aa3.patch_0` (along with its companion files `.gpu_resources` and `.stream`) into your Helldivers 2 game directory: `Helldivers 2\data\`. If `patch_0` already exists, you can rename it to `patch_1`, `patch_2`, etc.

---

## 3. Music Folder & Audio Format

### Where to put your music:
Place your music files in the MDL standard folder:
```text
%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\
```
*(Paste the above path into Windows Explorer address bar and press Enter; typical path: `C:\Users\<YourUsername>\AppData\Local\MDL\Helldivers2\StimMusic\`)*

### Supported Audio Format:
- **Standard 16-bit PCM WAV** (Mono or Stereo, 22.05kHz or 44.1kHz recommended).
- **Default filename**: `stim_music.wav`.
- **Multiple songs**: You can put multiple `.wav` files into the folder and switch between them in the in-game menu.
- **Audio Converter**:
  Double-click `convert_track.cmd` or drag any audio file onto it to convert it instantly to compatible 16-bit PCM WAV.

---

## 4. In-Game Settings Menu (ESC Menu)

Press `ESC` in-game -> Open **MDL Settings** -> Select **Stim Music**:

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **Enabled** | Toggle | On | Master toggle for Stim Music playback. |
| **Music Track** | Choice | Auto | Switch active music track from files found in the music folder. |
| **Music Volume (%)** | Slider | 100% | Adjust playback volume (0 - 100%) independently. |
| **Stim Length (ms)** | Slider | 6000ms | Playback window per stim (in ms). Resume point is preserved. |
| **Fade In (ms)** | Slider | 500ms | Volume fade-in transition duration (0 = immediate full volume). |
| **Fade Out (ms)** | Slider | 1500ms | Volume fade-out transition duration (0 = hard cut). |
| **Minimum Heal Threshold** | Slider | 1 | Minimum health gain required to trigger stim music (1-50). |
| **Hot Reload** | Toggle | On | Periodically checks music file and INI changes without restart. |

---

## 5. Configuration File (`STIM_MUSIC_CONFIG.ini`)

Located at `%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\STIM_MUSIC_CONFIG.ini`.
Settings are automatically updated when modified in the in-game menu:
```ini
# StimMusic configuration
enabled = 1
volume = 100
stim_ms = 6000
fade_in_ms = 500
fade_out_ms = 1500
min_heal = 1
hot_reload = 1
track = stim_music.wav
language = auto  # auto, en, or zh
```
