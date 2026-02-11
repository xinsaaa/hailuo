# 模型系列过滤Bug修复

## 问题描述

用户报告的问题：
1. 点击"全部"系列时，显示所有模型（正常）
2. 切换到"3.1系列"时，仍然显示所有模型（bug）
3. 单独打开"2.3"或"3.1"系列时，没有模型可选（bug）

## 根本原因

**字段名不匹配问题**：

前端代码使用了错误的字段名来过滤模型：
- 前端使用：`model.model_id`
- 后端返回：`model.id`（后端将数据库的`model_id`字段映射为`id`）

这导致过滤条件永远不会匹配，所以：
- 当选择"2.3系列"时，过滤条件`model.model_id.includes('2_3')`无法匹配任何模型
- 当选择"3.1系列"时，过滤条件`model.model_id.includes('3_1')`无法匹配任何模型
- 结果就是`filteredModels`要么是空数组，要么是所有模型（取决于初始值）

## 后端API返回的数据结构

```javascript
{
  "models": [
    {
      "id": "hailuo_2_3",           // ← 注意：字段名是 id，不是 model_id
      "name": "Hailuo 2.3",
      "display_name": "海螺 2.3",
      "description": "...",
      "price": 0.99,
      "is_default": true,
      "features": [...],
      "badge": "NEW",
      "supports_last_frame": false
    },
    ...
  ]
}
```

## 修复方案

将所有使用`model.model_id`的地方改为`model.id`：

### 修复前：
```javascript
// ❌ 错误：使用 model.model_id
filteredModels = modelsData.models.filter(model => 
  model.model_id.includes('2_0') || 
  model.model_id.includes('2_3') || 
  model.model_id.includes('hailuo_1_0')
)
```

### 修复后：
```javascript
// ✅ 正确：使用 model.id
filteredModels = modelsData.models.filter(model => 
  model.id.includes('2_0') || 
  model.id.includes('2_3') || 
  model.id.includes('hailuo_1_0')
)
```

## 修改的文件

`frontend/src/views/Dashboard.vue`

修改的地方：
1. 第133行：调试日志 - `m.model_id` → `m.id`
2. 第140-142行：2.3系列过滤条件 - `model.model_id` → `model.id`
3. 第145行：调试日志 - `m.model_id` → `m.id`
4. 第148-150行：3.1系列过滤条件 - `model.model_id` → `model.id`
5. 第153行：调试日志 - `m.model_id` → `m.id`
6. 第157行：调试日志 - `m.model_id` → `m.id`
7. 第161-169行：改进模型选择逻辑，添加智能切换

## 测试步骤

### 1. 清除浏览器缓存
```bash
# 按 Ctrl+Shift+Delete 清除缓存
# 或者使用无痕模式测试
```

### 2. 测试"2.3系列"
1. 访问 http://dadiai.cn:8000/dashboard
2. 点击"2.3系列"按钮
3. 打开浏览器控制台，查看调试信息：
   ```
   🔍 [DEBUG] 当前系列: 2.3
   🔍 [DEBUG] 2.3系列过滤结果: hailuo_2_3 - ¥0.99, hailuo_2_3_fast - ¥0.79, ...
   ```
4. 点击模型选择器，应该只显示2.3系列的模型：
   - Hailuo 2.3 (¥0.99)
   - Hailuo 2.3-Fast (¥0.79)
   - Hailuo 2.0 (¥1.19)
   - Hailuo 1.0系列 (¥0.49-0.59)

### 3. 测试"3.1系列"
1. 点击"3.1系列"按钮
2. 控制台应该显示：
   ```
   🔍 [DEBUG] 当前系列: 3.1
   🔍 [DEBUG] 3.1系列过滤结果: hailuo_3_1 - ¥1.59, hailuo_3_1_pro - ¥2.99, ...
   🔄 [DEBUG] 切换到新模型: hailuo_3_1 价格: 1.59
   ```
3. 点击模型选择器，应该只显示3.1系列的模型：
   - Hailuo 3.1 (¥1.59)
   - Hailuo 3.1-Pro (¥2.99)
   - Beta 3.1 (¥0.69)
   - Beta 3.1 Fast (¥0.35)

### 4. 测试"全部"
1. 点击"全部"按钮
2. 应该显示所有模型
3. 如果之前选中的模型在列表中，应该保持选中状态

### 5. 测试直接访问
1. 直接访问 http://dadiai.cn:8000/dashboard?series=2.3
2. 应该自动过滤并显示2.3系列模型
3. 直接访问 http://dadiai.cn:8000/dashboard?series=3.1
4. 应该自动过滤并显示3.1系列模型

## 预期结果

✅ 点击"2.3系列"，只显示2.3系列的4-5个模型
✅ 点击"3.1系列"，只显示3.1系列的4个模型
✅ 点击"全部"，显示所有10个模型
✅ 切换系列时，自动选择该系列的第一个模型
✅ 所有模型都显示正确的价格
✅ 底部"本次消耗"显示选中模型的价格

## 调试信息示例

### 正常的调试输出：
```
🔍 [DEBUG] 所有模型: hailuo_2_3 - ¥0.99, hailuo_2_3_fast - ¥0.79, hailuo_2_0 - ¥1.19, hailuo_3_1 - ¥1.59, ...
🔍 [DEBUG] 当前系列: 2.3
🔍 [DEBUG] 2.3系列过滤结果: hailuo_2_3 - ¥0.99, hailuo_2_3_fast - ¥0.79, hailuo_2_0 - ¥1.19, hailuo_1_0_director - ¥0.59, ...
🔍 [DEBUG] 最终可用模型: hailuo_2_3 - ¥0.99, hailuo_2_3_fast - ¥0.79, hailuo_2_0 - ¥1.19, hailuo_1_0_director - ¥0.59, ...
🔄 [DEBUG] 切换到新模型: hailuo_2_3 价格: 0.99
```

### 切换系列时：
```
🔍 [DEBUG] 当前系列: 3.1
🔍 [DEBUG] 3.1系列过滤结果: hailuo_3_1 - ¥1.59, hailuo_3_1_pro - ¥2.99, beta_3_1 - ¥0.69, beta_3_1_fast - ¥0.35
🔍 [DEBUG] 最终可用模型: hailuo_3_1 - ¥1.59, hailuo_3_1_pro - ¥2.99, beta_3_1 - ¥0.69, beta_3_1_fast - ¥0.35
🔄 [DEBUG] 切换到新模型: hailuo_3_1 价格: 1.59
```

## Git提交信息

```
commit 55ed5e3
Author: ...
Date: ...

fix: 修复模型系列过滤逻辑 - 使用正确的字段名model.id

- 将所有 model.model_id 改为 model.id 以匹配后端返回的数据结构
- 改进模型选择逻辑，切换系列时自动选择合适的模型
- 添加更详细的调试日志，包含模型ID和价格信息
- 修复了切换系列时模型列表为空的问题
```

## 相关文件

- `frontend/src/views/Dashboard.vue` - 前端Dashboard页面（已修复）
- `backend/main.py` - 后端API（返回model.id字段）
- `BUGFIX_DASHBOARD.md` - 之前的修复文档
- `BUGFIX_MODEL_FILTER.md` - 本次修复文档

## 注意事项

1. 确保清除浏览器缓存后测试
2. 检查浏览器控制台的调试信息
3. 如果问题仍然存在，检查后端API返回的数据结构
4. 确保后端服务正常运行
