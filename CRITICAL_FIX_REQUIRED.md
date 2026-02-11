# ⚠️ 关键修复步骤 - 必须执行

## 问题根源

代码已经修复完成，但是**服务器上的数据库没有重新初始化**！

当前API返回的数据：
- ❌ 只有8个模型（缺少 `hailuo_3_1` 和 `hailuo_3_1_pro`）
- ❌ 所有模型价格都是 ¥0.99（应该有不同价格）
- ❌ 过滤功能无法正常工作

## 🔧 立即执行以下步骤

### 方法1：删除数据库文件（推荐，最简单）

```bash
# 1. SSH连接到服务器
ssh user@dadiai.cn

# 2. 找到backend目录
cd /path/to/your/backend

# 3. 停止后端服务
pm2 stop backend
# 或者如果使用其他方式运行：
# kill <进程ID>

# 4. 删除数据库文件
rm database.db

# 5. 重启后端服务（会自动重新初始化数据库）
pm2 start backend
# 或者：
# python main.py
```

### 方法2：使用重置脚本（推荐，最安全）

```bash
# 1. SSH连接到服务器
ssh user@dadiai.cn

# 2. 进入backend目录
cd /path/to/your/backend

# 3. 运行重置脚本（会自动备份旧数据库）
# Linux/Mac:
bash reset_database.sh

# Windows:
reset_database.bat

# 或直接运行Python脚本:
python reset_models.py

# 4. 重启后端服务
pm2 restart backend
```

**重置脚本会自动：**
- ✅ 备份旧数据库
- ✅ 删除所有旧模型数据
- ✅ 初始化10个新模型
- ✅ 验证数据正确性
- ✅ 显示详细的模型列表

## ✅ 验证修复是否成功

### 1. 检查API返回
在浏览器或命令行执行：
```bash
curl http://dadiai.cn:8000/api/models
```

**应该看到：**
```json
{
  "models": [
    {"id": "hailuo_2_3", "price": 0.99, ...},
    {"id": "hailuo_2_3_fast", "price": 0.79, ...},
    {"id": "hailuo_2_0", "price": 1.19, ...},
    {"id": "hailuo_3_1", "price": 1.59, ...},
    {"id": "hailuo_3_1_pro", "price": 2.99, ...},
    {"id": "beta_3_1", "price": 0.69, ...},
    {"id": "beta_3_1_fast", "price": 0.35, ...},
    {"id": "hailuo_1_0_director", "price": 0.59, ...},
    {"id": "hailuo_1_0_live", "price": 0.59, ...},
    {"id": "hailuo_1_0", "price": 0.49, ...}
  ],
  "total": 10
}
```

**关键检查点：**
- ✅ total 应该是 10（不是8）
- ✅ 包含 hailuo_3_1 和 hailuo_3_1_pro
- ✅ 每个模型有不同的价格

### 2. 测试前端功能

1. **清除浏览器缓存**
   - 按 Ctrl+Shift+Delete
   - 或使用无痕模式

2. **打开控制台**
   - 按 F12
   - 切换到 Console 标签

3. **访问页面**
   ```
   http://dadiai.cn:8000/dashboard
   ```

4. **查看控制台输出**
   应该看到：
   ```
   🔍 [DEBUG] 模型总数: 10
   🔍 [DEBUG] 显示所有模型: 10 个
   ```

5. **测试2.3系列**
   - 点击"2.3系列"按钮
   - 应该显示6个模型
   - 价格应该正确显示

6. **测试3.1系列**
   - 点击"3.1系列"按钮
   - 应该显示4个模型（包括 hailuo_3_1, hailuo_3_1_pro, beta_3_1, beta_3_1_fast）
   - 价格应该正确显示

## 📊 预期结果

### 2.3系列（6个模型）：
- hailuo_2_3 - ¥0.99
- hailuo_2_3_fast - ¥0.79
- hailuo_2_0 - ¥1.19
- hailuo_1_0_director - ¥0.59
- hailuo_1_0_live - ¥0.59
- hailuo_1_0 - ¥0.49

### 3.1系列（4个模型）：
- hailuo_3_1 - ¥1.59
- hailuo_3_1_pro - ¥2.99
- beta_3_1 - ¥0.69
- beta_3_1_fast - ¥0.35

## 🚨 如果问题仍然存在

### 检查后端日志
```bash
# 查看PM2日志
pm2 logs backend

# 或查看日志文件
tail -f logs/app.log
```

### 确认数据库位置
```bash
# 在backend目录中查找数据库文件
ls -la *.db

# 确认是否有多个数据库文件
find . -name "*.db"
```

### 手动检查数据库
```bash
# 使用sqlite3查看数据库
sqlite3 database.db

# 在sqlite3中执行：
SELECT model_id, price, sort_order FROM aimodel ORDER BY sort_order;

# 应该看到10行数据，每行有不同的价格
```

## 📝 技术说明

### 为什么需要重新初始化？

`init_default_models()` 函数有一个保护机制：
```python
existing = session.exec(select(AIModel)).first()
if existing:
    return  # 已有数据，跳过初始化
```

这意味着：
- 如果数据库中已经有模型数据，不会自动更新
- 必须删除旧数据或删除整个数据库文件
- 重启后端会自动创建新的数据库并初始化正确的数据

### 代码修复已完成

前端修复（Dashboard.vue）：
- ✅ 使用正确的字段名 `model.id` 而不是 `model.model_id`
- ✅ 改进3.1系列过滤逻辑
- ✅ 添加详细的调试日志
- ✅ 添加watch监听器自动更新模型

后端修复（main.py）：
- ✅ 10个模型定义完整
- ✅ 每个模型有正确的价格
- ✅ sort_order 正确（1-10）
- ✅ API返回包含price字段

## 🎯 下一步

1. **立即执行**上面的数据库重置步骤
2. **验证**API返回10个模型
3. **测试**前端过滤功能
4. **确认**价格显示正确

如果完成以上步骤后问题仍然存在，请提供：
- API返回的完整数据
- 浏览器控制台的输出
- 后端日志
