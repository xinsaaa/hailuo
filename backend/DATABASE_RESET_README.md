# 数据库重置指南

## 🚨 问题症状

如果你遇到以下问题：
- ❌ 模型过滤不工作
- ❌ 所有模型价格都是¥0.99
- ❌ 只显示8个模型（缺少hailuo_3_1和hailuo_3_1_pro）
- ❌ 切换系列后模型不更新

**原因：数据库需要重新初始化！**

## 🔧 快速修复（3步）

### 步骤1：重置数据库

选择以下任一方法：

**方法A：使用脚本（推荐）**
```bash
# Linux/Mac
bash reset_database.sh

# Windows
reset_database.bat

# 或直接运行Python脚本
python reset_models.py
```

**方法B：手动删除**
```bash
# 停止服务
pm2 stop backend

# 删除数据库
rm database.db

# 启动服务（会自动重新初始化）
pm2 start backend
```

### 步骤2：验证数据

```bash
# 运行验证脚本
python verify_models.py
```

**应该看到：**
```
✅ 模型数量正确
✅ 所有必需模型都存在
✅ 所有价格设置正确
✅ 验证通过！模型数据正确！
```

### 步骤3：测试API

```bash
# 测试API端点
curl http://localhost:8000/api/models

# 或在浏览器中访问
http://localhost:8000/api/models
```

**应该返回：**
- `"total": 10` （不是8）
- 包含 `hailuo_3_1` 和 `hailuo_3_1_pro`
- 每个模型有不同的价格

## 📊 正确的模型列表

重置后应该有10个模型：

### 2.3系列（6个）
1. hailuo_2_3 - ¥0.99
2. hailuo_2_3_fast - ¥0.79
3. hailuo_2_0 - ¥1.19
4. hailuo_1_0_director - ¥0.59
5. hailuo_1_0_live - ¥0.59
6. hailuo_1_0 - ¥0.49

### 3.1系列（4个）
7. hailuo_3_1 - ¥1.59
8. hailuo_3_1_pro - ¥2.99
9. beta_3_1 - ¥0.69
10. beta_3_1_fast - ¥0.35

## 🛠️ 可用的脚本

### reset_models.py
完整的重置脚本，会：
- 删除所有旧模型
- 初始化10个新模型
- 显示详细的验证信息

```bash
python reset_models.py
```

### verify_models.py
验证脚本，检查：
- 模型数量（应该是10）
- 所有必需模型是否存在
- 价格是否正确
- 系列分组是否正确

```bash
python verify_models.py
```

### reset_database.sh / reset_database.bat
自动化脚本，会：
- 备份旧数据库
- 删除数据库文件
- 运行reset_models.py
- 显示下一步操作

```bash
# Linux/Mac
bash reset_database.sh

# Windows
reset_database.bat
```

## ❓ 常见问题

### Q: 重置会丢失数据吗？
A: 不会！只会重置模型定义，不会影响：
- 用户账号
- 订单记录
- 交易记录
- 其他业务数据

### Q: 为什么需要重置？
A: `init_default_models()`函数有保护机制：
```python
if existing:
    return  # 已有数据，跳过初始化
```
所以必须先删除旧数据才能初始化新数据。

### Q: 如何确认重置成功？
A: 运行验证脚本：
```bash
python verify_models.py
```
应该看到所有检查都通过（✅）。

### Q: 重置后还是有问题？
A: 检查以下几点：
1. 后端服务是否重启
2. 是否有多个数据库文件
3. 浏览器缓存是否清除
4. 查看后端日志是否有错误

## 📞 需要帮助？

如果问题仍然存在，请提供：
1. `verify_models.py` 的输出
2. API返回的数据
3. 后端日志
4. 浏览器控制台输出

## 📚 相关文档

- `CRITICAL_FIX_REQUIRED.md` - 详细的修复步骤
- `SOLUTION_SUMMARY.md` - 完整的解决方案总结
- `DEBUG_GUIDE.md` - 调试指南
- `BUGFIX_MODEL_FILTER.md` - Bug修复文档

## ✅ 检查清单

完成以下步骤后，问题应该解决：

- [ ] 运行 `reset_models.py` 或 `reset_database.sh`
- [ ] 看到 "✅ 已添加 10 个新模型"
- [ ] 运行 `verify_models.py`
- [ ] 看到 "✅ 验证通过！模型数据正确！"
- [ ] 重启后端服务
- [ ] 测试API返回10个模型
- [ ] 清除浏览器缓存
- [ ] 测试前端过滤功能
- [ ] 确认价格显示正确

全部完成后，问题应该彻底解决！🎉
