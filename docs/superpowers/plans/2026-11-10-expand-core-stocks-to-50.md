# 板块核心个股主力排行扩充至 Top 50 实施计划

## 目标
将板块核心个股主力排行从原本的 10 只扩展到 50 只，并在前端提供良好的滚动展示与标题反馈，确保测试通过与前端构建更新。

---

### Task 1: 后端接口扩展与单元测试更新 (TDD)
- **Files**:
  - `backend/app/main.py`
  - `backend/tests/test_main.py`
- **步骤**:
  1. 在 `backend/tests/test_main.py` 中更新测试，断言 `pz` 默认参数为 `"50"`，并增加传参 `limit=30` 测试。
  2. 运行 pytest 观察预期内的断言失败。
  3. 修改 `backend/app/main.py` 中 `get_sector_stocks(code: str, limit: int = 50)`，将东财 params 中的 `pz` 设为 `str(min(max(limit, 1), 100))`。
  4. 运行 pytest 验证全部测试通过。

### Task 2: 前端展示优化与重新打包构建
- **Files**:
  - `frontend/src/App.vue`
- **步骤**:
  1. 修改 `frontend/src/App.vue` 中的标题与序号布局，自适应显示当前拉取到的个股条数（如 `Top 50`）。
  2. 运行 `npm run build`，编译生成最新的 `frontend/dist` 静态资源。
  3. 验证静态构建成功无语法错误。

### Task 3: 整体验证
- **步骤**:
  1. 运行完整后端测试套件 `PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v`。
  2. 验证构建产物在 `frontend/dist` 正常生效。
