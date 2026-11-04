# 《绝地潜兵 2》MDL3 模组修复与适配实战指南 (Cheat Sheet)

> 整理自「霸王虫血量显示模组」从旧版 (BSL / FFI / 内存直读) 向 **MDL3 (`3.0.0-dev.21+`)** + **HD2 Data Hub (`0.3.0+`)** 完整迁移的实战经验。供后续快速修复、移植或开发其他 HD2 脚本模组参考。

---

## 一、失效根因分析与架构对比

| 维度 | 旧版模组模式 (已失效) | MDL3 + Data Hub 现代模式 (标准做法) |
| :--- | :--- | :--- |
| **执行环境** | LuaJIT (`require('ffi')` 调 Win32 API) | **纯 PUC Lua 5.1**（MDL3 游戏虚拟机禁用了 FFI） |
| **数据来源** | 硬编码游戏 PE 校验码 + 固定 RVA 内存直读 (`ReadProcessMemory`) | **事件总线驱动**（通过公开的全局只读接口 `_G.HD2Data`） |
| **版本耐受性** | 游戏每次更新导致 PE 头 / 内存偏移变更即闪退失效 | **跨游戏版本免疫**（由 Data Hub 底层统一适配，上层零偏移依赖） |
| **安全性** | 触碰未解密代码页易引起反作弊拦截或非法内存访问崩溃 | **严格只读、零内存写入、零 FFI**，完全合规安全 |
| **界面绘制** | 简陋调试字体，或猜错 Stingray 材质 API 导致崩溃 | **原生游戏 UI 字体**（支持中英双语、字库探测降级、ESC 实时预览置顶） |

---

## 二、MDL3 模组规范与打包规则

### 1. 源码文件规范
- **第一行强制声明插件标识**（MDL3 加载器识别所必需）：
  ```lua
  -- HD2-Addon: mods/<author>/<mod_name>
  ```
- **纯 7-bit ASCII 源码编码**：
  PUC Lua 5.1 解析非 ASCII 字符可能因平台编码差异产生乱码或语法错误。中文字符串建议使用十进制转义序列（例如 `'\233\156\184\231\142\139\232\153\171'` 表示 `"霸王虫"`）。
- **静态 API 白名单限制**：
  绝不能调用未许可的敏感 API（如 `WriteProcessMemory`、`VirtualProtect`、未授权的 `stingray` 命名空间）。

### 2. 补丁归档格式 (`.patch_0`)
- **Stingray 补丁魔数**：`0xF0000011`。
- **资源类型**：Lua 资源类型标识为 `e217d12cfa8d4ea1`。
- **Hash 算法**：Lua 资源路径使用 **MurmurHash64A**（种子为 `0`）。
- **Envelope 封包**：每个 Lua 资源的头部必须携带 8 字节包头（`u32 body_length` + `u32 version = 2`）。

---

## 三、HD2 Data Hub (`_G.HD2Data` API 1) 接入核心技巧

### 1. 识别与过滤目标实体
```lua
local HIVE_LORD_SEMANTIC = 'enemy/v1/terminids/hive_lord'
local HIVE_LORD_TYPE_HEX = 'D465D9C7F77A07CB'

local function is_target_enemy(e)
    if type(e) ~= 'table' then return false end
    -- 1. 优先匹配语义目录标识
    if e.semantic_id == HIVE_LORD_SEMANTIC then return true end
    -- 2. 实体包装对象匹配
    if type(e.entity) == 'table' and type(e.entity.is) == 'function' then
        if e.entity:is(HIVE_LORD_SEMANTIC) == true then return true end
    end
    -- 3. 兼容回退匹配 64 位类型哈希（即使 semantic_id 缺失也能兜底）
    if type(e.type) == 'string' and e.type:upper() == HIVE_LORD_TYPE_HEX then return true end
    return false
end
```

### 2. 关键避坑：致死事件必须监听 `entity_died`！
> **Data Hub 核心机理**：当单位生命状态切入死亡（`life >= 2`）时，Data Hub 内部通过 `if life >= 2 then emit('entity_died')` 分支处理，**会跳过后续的 `elseif emit('entity_damaged')` 分支**！
> **后果**：如果只监听 `entity_damaged`，最后一击击杀目标时血量**永远卡在死前的残血状态，不会归零**。

```lua
-- 必须同时订阅这 5 个基础事件
local EVENT_HANDLERS = {
    { 'mission_started', on_mission_started },
    { 'mission_ended',   on_mission_ended   },
    { 'entity_spawned',  on_entity_spawned  },
    { 'entity_damaged',  on_entity_damaged  },
    { 'entity_died',     on_entity_died     }, -- ★ 致命一击归零的唯一来源
}
```

### 3. 中途加入战局挂载 (`Mid-Fight Attach`)
如果玩家中途加入任务，霸王虫可能早已生成（错过了 `entity_spawned`）。必须在 `entity_damaged` 中添加自动建档逻辑：
```lua
local rec = M.records[id]
if not rec then
    rec = { id = id, hp = hp, max = max_hp, spawned_at = M.clock }
    M.records[id] = rec -- 即刻挂载，避免血条不显示
end
```

### 4. 潜地状态保持与破土血量继承
- 霸王虫潜地钻入地下时，引擎的实体句柄会短暂变为无效（`is_valid() == false`）。**切勿立即清除记录**，否则会导致血条瞬间闪退消失；应标记 `burrowed = true`，进入保留倒计时。
- 当它再次破土时，引擎可能会分配一个新的 `entity_id`。在 `on_entity_spawned` 中必须通过未死亡且处于潜地状态的旧记录进行继承（`HIVE_LORD_RESURFACE`），**防止血条误刷回 100% 满血**。

### 5. 掉线重连与 Hub 热重载自愈
```lua
local function hub_tick()
    local D = rawget(_G, 'HD2Data')
    if not D or tonumber(D.api) ~= 1 then return end
    
    -- 若 Data Hub 表指针发生变化（说明 Hub 发生了热重载），注销旧订阅并重新绑定
    if D ~= M.hub_ref then
        unsubscribe_all()
        M.hub_ref = D
    end
    
    -- 周期性检查 sub:active()，自动恢复被异常丢弃的订阅
    for _, pair in ipairs(EVENT_HANDLERS) do
        local name, fn = pair[1], pair[2]
        if not sub_is_active(M.subs[name]) then
            M.subs[name] = D.on(name, fn, { owner = ADDON_ID, id = name, priority = 50 })
        end
    end
end
```

---

## 四、Stingray 引擎 GUI 绘制与防崩溃军规

> 以下规则总结自参考模组（战地5击杀反馈 v2.0.0）与崩溃用例排查，每一条都曾对应引擎直接闪退。

### 1. Stingray 构造器类型判定 (`is_ctor`)
- **陷阱**：在游戏 VM 中，`stingray.Vector2`、`stingray.Vector3`、`stingray.Color` 是带有 `__call` 元表的类表（提供静态方法与构造函数），`type(v)` 返回的是 `'table'` 而非 `'function'`！
- **修复规则**：
  ```lua
  local function is_ctor(v)
      local t = type(v)
      return t == 'function' or t == 'table' or t == 'userdata'
  end
  ```

### 2. `IdString64.from_hex` 绝对不能跨帧缓存
- **陷阱**：Stingray 的 `IdString64` 属于帧临时分配（Frame-temporary），一旦跨帧复用，底层引擎会访问野指针导致游戏闪退。
- **修复规则**：
  每次重绘文本图层时，**必须在当帧内即时通过 `IdString64.from_hex(hex)` 生成 ID**，且在绑定前通过 `Application.can_get` 确认资源（`font`、`material`、`texture`）已就绪。

### 3. 原生游戏字体 (`MDL3.ui.fonts`) 严禁调用更新与单个销毁
- **陷阱**：原生 UI 字体文本句柄**绝对不能传递给 `Gui.update_text` 或 `Gui.destroy_text`**，否则引擎会产生未定义行为甚至崩溃。
- **标准双层分离架构**：
  - **底层 `M.gui`（矩形槽）**：承载血条背景、底槽、受击残影槽、当前生命条等 4 个矩形句柄。矩形句柄完全支持且推荐使用 `Gui.update_rect` 进行原地平滑刷新。
  - **顶层 `M.text_gui`（独立文本层）**：在 `M.gui` 之后创建微型专用屏幕 GUI，专门绘制原生 UI 字体。当文字内容改变时，**直接使用 `World.destroy_gui(world, text_gui)` 整体替换该微型图层**。
  - **限流控制**：高频掉血时对文本图层的整层重建进行频率限制（如 `<= 20 Hz`，即 `interval >= 0.05s`）。

### 4. CJK 字库探测与自动降级（防方块/问号乱码）
- 当玩家使用的游戏客户端未安装或未加载中文语言字库时，直接渲染中文字符会在原生字体中呈现为方形方块或 `???`。
- **探测逻辑**：
  ```lua
  -- 测量中文字符与 "???" 在当前字体下的像素宽度
  local sw = Gui.text_extents(target_gui, '霸王虫', fid, 20)
  local qw = Gui.text_extents(target_gui, '???', fid, 20)
  -- 若宽度完全一致，说明当前字库缺少 CJK 字符集，全部回退显示为 "?"
  local has_cjk = not (sw ~= nil and qw ~= nil and math.abs(sw - qw) < 0.01)
  -- 降级为纯英文字符串 'HIVE LORD'
  ```

### 5. ESC 菜单置顶预览机制
- **问题**：玩家在战斗或舰桥按 `ESC` 打开 `MDL 设置` 拖动血条缩放/位置滑块时，MDL3 自身的设置面板 (`MDL3.panel`) 会重建并覆盖在 Mod 原有 GUI 之上，导致玩家无法边调边看。
- **置顶机制**：
  监控 `MDL3.panel.builds` 与 `MDL3.options.revision`。检测到面板重建时，延时 `0.14s` 销毁并重建本 Mod 的 HUD GUI。后创建的 Screen GUI 会自动绘制在更先创建的设置菜单前方。

### 6. 世界对象销毁保护 (`World.destroy_gui`)
- 必须确保销毁目标属于当前存活的世界列表：
  ```lua
  local function world_by_identity(worlds, wanted)
      if wanted == nil then return false end
      for _, v in pairs(worlds or {}) do
          if v == wanted then return true end -- 必须严格进行引用同一性比较
      end
      return false
  end
  ```
  在进出任务发生世界切换时，严禁在已析构的旧世界句柄上调用 `World.destroy_gui`。

---

## 五、快速修复与移植模组核对清单 (Checklist)

下次拿到需要修复的旧版模组时，按照以下步骤依次执行：

### 第一步：排查并清理旧代码
- [ ] 搜索并移除所有 `require('ffi')` 及 Win32 C 声明 (`ffi.cdef`)。
- [ ] 搜索并移除 `ReadProcessMemory`、`GetModuleHandleA`、PE 头校验函数。
- [ ] 搜索并移除所有硬编码十六进制内存偏移（如 `0x3326688`）。

### 第二步：接入 Data Hub 数据层
- [ ] 在 `Source/mods/<author>/<mod>.lua` 首行添加 `-- HD2-Addon: ...`。
- [ ] 添加 `hub_tick()`，订阅 `HD2Data` 对应事件（怪物血量订 `entity_damaged` + `entity_died`；击杀反馈订 `player_hit` / `player_kill_credited` / `player_damage_dealt` 等）。
- [ ] 确保实现致命一击归零与中途参战挂载。

### 第三步：重构 GUI 渲染层
- [ ] 引入 `is_ctor` 保护 `Vector2` / `Vector3` / `Color` 判定。
- [ ] 确保 `IdString64.from_hex` 每帧现场创建，不保存在全局或持久表中。
- [ ] 文本层与矩形层拆分：原生字体放独立的微型 GUI，绝不调用 `update_text`；调试字体做备用回退。
- [ ] 添加 `Gui.text_extents` CJK 探测，防止非中文客户端出现 `???` 乱码。

### 第四步：打包与双重验收
- [ ] 使用 `archive.py` 生成 `.patch_0` 归档。
- [ ] 打包为 `.zip`（包含 `Addon/9ba626afa44a3aa3.patch_0`、`manifest.json`、`README.md`）。
- [ ] 运行静态检查工具，确认无越界引擎 API 与内存写操作。
- [ ] 使用真实 MDL3 `mods.discover` 扫描验证归档，确保输出 `rejected = 0, warnings = ""`。
- [ ] 运行离线模拟断言与变异测试，确保所有异常分支（潜地、掉线、断开、重载）均被正确捕获。
