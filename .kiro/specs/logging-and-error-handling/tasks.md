# Implementation Plan

- [ ] 1. 设置项目依赖和基础配置
  - 安装 loguru 和 hypothesis 依赖包
  - 创建日志目录结构
  - 添加环境变量配置
  - _Requirements: 1.1, 7.1_

- [ ] 2. 实现核心日志模块
- [ ] 2.1 创建 Logger 配置模块
  - 实现 `backend/logger.py` 核心日志器
  - 配置 loguru 的多个处理器（控制台、文件、审计）
  - 实现日志级别从环境变量读取
  - 实现开发/生产模式的不同输出格式
  - _Requirements: 1.1, 1.2, 1.5_

- [ ]* 2.2 编写 Logger 配置的属性测试
  - **Property 1: Structured Log Format**
  - **Validates: Requirements 1.2**

- [ ] 2.3 实现敏感信息脱敏功能
  - 创建敏感字段检测函数
  - 实现自动脱敏过滤器
  - 添加到 loguru 配置中
  - _Requirements: Non-Functional Security_

- [ ]* 2.4 编写敏感信息脱敏的单元测试
  - 测试密码、token 等字段被正确脱敏
  - 测试嵌套对象的脱敏
  - _Requirements: Non-Functional Security_

- [ ] 3. 实现请求上下文管理
- [ ] 3.1 创建上下文变量模块
  - 实现 `backend/middleware/context.py`
  - 定义 request_id_var 和 user_id_var
  - 实现 get/set 辅助函数
  - 实现 request_id 生成函数
  - _Requirements: 3.1, 3.2_

- [ ]* 3.2 编写请求 ID 唯一性的属性测试
  - **Property 3: Request ID Uniqueness**
  - **Validates: Requirements 3.1**

- [ ] 3.3 实现 Request ID 中间件
  - 创建 `backend/middleware/request_id.py`
  - 为每个请求生成唯一 ID
  - 将 ID 存储到上下文变量
  - 将 ID 添加到响应头
  - _Requirements: 3.1, 3.2, 3.4_

- [ ]* 3.4 编写 Request ID 中间件的属性测试
  - **Property 6: Response Header Inclusion**
  - **Validates: Requirements 3.4**

- [ ] 4. 实现日志中间件
- [ ] 4.1 创建 Logging 中间件
  - 实现 `backend/middleware/logging.py`
  - 记录请求开始和结束
  - 计算请求处理时间
  - 自动注入 request_id 到日志
  - _Requirements: 1.3, 3.3_

- [ ]* 4.2 编写日志中间件的属性测试
  - **Property 2: Request ID Propagation**
  - **Validates: Requirements 3.3**

- [ ] 5. 实现全局异常处理
- [ ] 5.1 创建自定义异常类
  - 实现 `backend/exceptions.py`
  - 定义 AppException 基类
  - 实现 ValidationException
  - 实现 AuthenticationException
  - 实现 AuthorizationException
  - 实现 NotFoundException
  - _Requirements: 2.3, 2.4, 2.5_

- [ ] 5.2 实现全局异常处理器
  - 创建 `backend/middleware/exception_handler.py`
  - 实现 global_exception_handler 函数
  - 捕获所有未处理异常
  - 记录完整堆栈跟踪
  - 返回标准化错误响应
  - _Requirements: 2.1, 2.2_

- [ ]* 5.3 编写异常处理的属性测试
  - **Property 4: Exception Logging**
  - **Property 5: Standardized Error Response**
  - **Property 7: Error Response Request ID**
  - **Validates: Requirements 2.1, 2.2, 3.5**

- [ ]* 5.4 编写验证错误格式的属性测试
  - **Property 8: Validation Error Format**
  - **Validates: Requirements 2.3**

- [ ] 6. 集成中间件到 FastAPI 应用
- [ ] 6.1 更新 main.py 注册中间件
  - 导入所有中间件
  - 按正确顺序注册中间件
  - 注册全局异常处理器
  - 配置 FastAPI 异常处理
  - _Requirements: 2.1, 3.1, 3.3_

- [ ] 6.2 更新现有代码使用新日志系统
  - 替换 print 语句为 logger 调用
  - 更新 automation.py 使用新日志器
  - 更新 admin.py 使用新日志器
  - 更新其他模块使用新日志器
  - _Requirements: 6.1, 6.2, 6.5_

- [ ]* 6.3 编写模块名检测的属性测试
  - **Property 9: Module Name Detection**
  - **Validates: Requirements 6.2**

- [ ] 7. 实现审计日志功能
- [ ] 7.1 创建审计日志辅助函数
  - 在 logger.py 中添加 audit() 方法
  - 实现审计日志专用文件处理器
  - 定义审计事件类型枚举
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 7.2 在关键业务操作中添加审计日志
  - 用户注册时记录审计日志
  - 用户登录时记录审计日志
  - 管理员操作时记录审计日志
  - 支付完成时记录审计日志
  - 订单创建时记录审计日志
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ]* 7.3 编写审计日志的单元测试
  - 测试审计日志格式正确
  - 测试审计日志包含所有必需字段
  - 测试审计日志写入独立文件
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 8. 实现日志轮转和清理
- [ ] 8.1 配置日志文件轮转
  - 配置基于大小的轮转（100MB）
  - 配置 gzip 压缩
  - 配置日志文件命名格式
  - _Requirements: 1.4, 7.2, 7.3_

- [ ] 8.2 实现日志清理任务
  - 创建 `backend/tasks/log_cleanup.py`
  - 实现删除 30 天前日志的函数
  - 添加定时任务调度
  - _Requirements: 7.4_

- [ ]* 8.3 编写日志轮转的集成测试
  - 测试日志文件达到大小限制时轮转
  - 测试轮转后文件被压缩
  - 测试旧日志文件被删除
  - _Requirements: 1.4, 7.2, 7.3, 7.4_

- [ ] 9. 实现动态日志级别管理
- [ ] 9.1 创建日志管理 API
  - 在 admin.py 中添加 GET /api/admin/logs/level 端点
  - 在 admin.py 中添加 PUT /api/admin/logs/level 端点
  - 实现日志级别验证
  - 实现动态更新日志级别
  - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [ ]* 9.2 编写日志级别管理的单元测试
  - 测试获取当前日志级别
  - 测试更新日志级别
  - 测试无效日志级别被拒绝
  - _Requirements: 4.1, 4.2, 4.5_

- [ ]* 9.3 编写无效日志级别的属性测试
  - **Property 11: Invalid Log Level Rejection**
  - **Validates: Requirements 4.5**

- [ ] 10. 实现日志查询和导出功能
- [ ] 10.1 创建日志查询 API
  - 在 admin.py 中添加 GET /api/admin/logs/query 端点
  - 实现按时间范围过滤
  - 实现按日志级别过滤
  - 实现按模块过滤
  - 实现按 request_id 搜索
  - _Requirements: 8.2, 8.3_

- [ ] 10.2 实现日志导出功能
  - 在 admin.py 中添加 GET /api/admin/logs/export 端点
  - 实现 JSON 格式导出
  - 实现 CSV 格式导出
  - _Requirements: 8.5_

- [ ]* 10.3 编写日志查询的集成测试
  - 测试按不同条件过滤日志
  - 测试按 request_id 搜索
  - 测试导出功能
  - _Requirements: 8.2, 8.3, 8.5_

- [ ] 11. 实现日志统计和分析
- [ ] 11.1 创建日志统计 API
  - 在 admin.py 中添加 GET /api/admin/logs/stats 端点
  - 实现错误统计聚合
  - 实现按时间段统计
  - 实现按模块统计
  - _Requirements: 8.4_

- [ ]* 11.2 编写日志统计的单元测试
  - 测试错误统计计算正确
  - 测试时间段统计
  - 测试模块统计
  - _Requirements: 8.4_

- [ ] 12. 编写集成测试和文档
- [ ]* 12.1 编写端到端集成测试
  - 测试完整请求流程的日志记录
  - 测试异常场景的错误处理
  - 测试审计日志的完整性
  - _Requirements: All_

- [ ]* 12.2 编写 async 上下文的单元测试
  - 测试异步函数中的上下文传递
  - 测试并发请求的上下文隔离
  - _Requirements: 6.3_

- [ ] 12.3 更新项目文档
  - 更新 README 添加日志系统说明
  - 创建日志配置指南
  - 创建故障排查指南
  - 添加日志查询示例
  - _Requirements: All_

- [ ] 13. 性能优化和生产准备
- [ ] 13.1 实现日志采样功能
  - 在高流量场景下实现日志采样
  - 配置采样率
  - 确保错误日志不被采样
  - _Requirements: Non-Functional Performance_

- [ ] 13.2 配置生产环境日志
  - 配置日志聚合（可选）
  - 配置监控告警
  - 配置日志备份
  - _Requirements: Non-Functional Reliability_

- [ ]* 13.3 进行性能测试
  - 测试日志系统对请求延迟的影响
  - 测试高并发下的日志性能
  - 测试日志文件 I/O 性能
  - _Requirements: Non-Functional Performance_

- [ ] 14. 最终检查点 - 确保所有测试通过
  - 运行所有单元测试
  - 运行所有属性测试
  - 运行所有集成测试
  - 验证日志系统在开发和生产模式下正常工作
  - 确认所有审计日志正确记录
  - 验证异常处理和错误响应格式
