# StimMusic v2.0.0 — 打针放音乐 (MDL3 + HD2 Data Hub 现代重构版)

> 本模组已按照《MDL3 模组修复与适配指南》全面迁移至 **MDL3 (3.0.0-dev.21+)** 与 **HD2 Data Hub (0.3.0+)** 现代架构。纯 PUC Lua 5.1 编写，移除旧版 FFI 与硬编码内存依赖，安全稳定，跨版本免疫。

---

## 一、安装与前置要求

1. **前置模组**：
   - **MDL3** (3.0.0-dev.21 或更高版本)
   - **HD2 Data Hub** (0.3.0 或更高版本，`HD2Data` API 1)
   *(不再依赖旧版 Bingus Shared Loader 或 HD2Runtime)*
2. **安装方法**：
   - **Arsenal 模组管理器**：直接导入本模组（或直接启用当前模组），点 **Deploy** 部署。确保 MDL3 位于高优先级。
   - **手动安装**：将 `Addon/9ba626afa44a3aa3.patch_0` 放入游戏 `data` 目录对应补丁编号。

---

## 二、音乐放在哪里与支持格式

### 1. 存放目录
模组优先读取 MDL 官方标准专用目录下的音乐文件：
```text
%LOCALAPPDATA%\MDL\Helldivers2\StimMusic\
```
*(在你的电脑上对应路径为：`C:\Users\kugua\AppData\Local\MDL\Helldivers2\StimMusic\`)*

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

### 3. 音频格式要求与性能优化 (战地5方案)
- **推荐格式**：**MS-ADPCM WAV (强烈推荐)**
  - 基于战地5击杀音效方案，XAudio2 原生硬件级解码。
  - 体积比传统 PCM **缩小约 75%**（32MB 歌曲缩减至 8.7MB，每 6 秒分片仅 ~290KB）。
  - 极大降低 Lua base64 转换与 IPC 吞吐开销，**彻底消除切歌与播放时的间歇性卡顿/掉帧**。
- **兼容格式**：**16-bit PCM WAV**（完全向后兼容）。
- **一键高效转码工具**：
  模组目录及压缩包中已自带 `convert_track.cmd`。
  - **拖拽模式**：直接把歌曲文件（.mp3 / .flac / .m4s / .wav）拖拽到 `convert_track.cmd` 图标上，自动生成 MS-ADPCM 48kHz 高性能 WAV。
  - **批量模式**：双击运行 `convert_track.cmd`，自动扫描当前目录下的音频文件，并将大体积 PCM WAV 压缩转码为 MS-ADPCM。
  - **手动命令**：
    ```cmd
    ffmpeg -y -i "input.mp3" -map 0:a:0? -ac 2 -ar 48000 -c:a adpcm_ms -block_size 1024 "stim_music.wav"
    ```

---

## 三、怎么热更新 (免重启游戏生效)

1. **自动指纹检测机制**：
   - 当游戏处于运行状态时，模组每 2 秒会自动对音乐文件的大小与文件头指纹（Fingerprint）进行检测。
2. **免重启实时生效场景**：
   - **替换歌曲**：直接将新的 `stim_music.wav` 覆盖到文件夹中，模组检测到文件大小/内容改变后，在 2 秒内自动重新载入、重分段，并在下一次扎针时播放新曲目。
   - **换歌配置**：在 `STIM_MUSIC_CONFIG.ini` 中修改 `track = yu_ai.wav`，保存后 2 秒内自动生效。
   - **游戏内实时切换**：按 `ESC` -> **MDL 设置** -> **打针放音乐 (Stim Music)**，在「当前音乐 (Music Track)」中切换曲目，即刻生效！

---

## 四、MDL 设置界面 (游戏内 ESC 菜单)

进入游戏后按 `ESC` -> 打开 **MDL 设置** -> 点击 **打针放音乐 (Stim Music)**，即可看到全部可调选项：

| 选项名称 | 类型 | 说明 |
| :--- | :--- | :--- |
| **总开关 (Enabled)** | 开关 (Toggle) | 开启或关闭打针音乐功能。 |
| **当前音乐 (Music Track)** | **单选 (Choice)** | **直接显示当前加载的音乐文件名**（如 `stim_music.wav`、`yu_ai.wav` 等），支持游戏内直接切换曲目！ |
| **音乐音量 (Volume %)** | 滑块 (Slider) | 0 ~ 100% 独立调节打针音乐音量，不影响游戏主音量。 |
| **针剂时长 (Stim Length ms)** | 滑块 (Slider) | 针剂效果窗口持续时间（默认 6000 毫秒）。 |
| **最小回血量判定 (Min Heal)** | 滑块 (Slider) | 触发判定的最小治疗增量（默认 1，防强化剂误触可调至 8~10）。 |
| **自动检测更新 (Hot Reload)** | 开关 (Toggle) | 开启后每 2 秒检测文件改动，免重启热更新。 |

---

## 五、状态监控与排查

- **实时状态文件**：
  `%LOCALAPPDATA%\CowboyBingus\Helldivers2\StimMusic\STIM_MUSIC_STATUS.txt`
  游戏运行时自动记录当前播放状态、生效文件名、针剂计数、Hub 连接等。
- **运行日志文件**：
  `%LOCALAPPDATA%\CowboyBingus\Helldivers2\StimMusic\stim_music.log`
