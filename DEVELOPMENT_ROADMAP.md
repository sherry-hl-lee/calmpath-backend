# CalmPath Backend Development Roadmap

## 当前唯一目标

本阶段只实现下面这个 User Story：

> As a sensory-sensitive commuter, I want to identify nearby sensory refuge locations such as parks, libraries, and quiet public spaces, so that I can take breaks when feeling overwhelmed.

## Acceptance Criteria

1. 用户可以根据当前位置和搜索半径搜索附近的 sensory refuge。
2. 搜索结果至少显示 refuge 的名称、类型和距离。
3. refuge 可以显示在地图上，因此结果需要包含位置坐标。
4. 用户选择一个 refuge 后，可以看到完整地址。
5. 数据来自 Melbourne public facilities 和 open space datasets。

## 明确不做的事情

当前阶段不做：

- 路线规划
- 拥挤人流避让
- High/Low sensory indicator
- 公共交通路线
- 实时行人路线推荐
- 其他 User Story

如果开发过程中出现新的想法，先记录下来，不要直接加入当前功能。

---

# 总体开发流程

```text
确认 User Story
    ↓
设计最小 API
    ↓
先用假数据做出可以调用的接口
    ↓
用 FastAPI /docs 测试
    ↓
和前端确认接口
    ↓
和数据库开发者确认真实数据字段
    ↓
接入真实数据
    ↓
编写自动化测试
    ↓
前端联调
    ↓
创建 Pull Request
    ↓
Review 后合并到 development
```

不要一开始就同时做数据库、前端、地图和完整业务逻辑。先让一条最小 API 跑起来。

---

# Stage 0 - 准备本地开发环境

## 目标

确认本地 backend 仓库可以运行。

## 已有基础结构

```text
app/
  main.py
  api/routes/
  schemas/
  services/
  models/
tests/
docs/api/
```

## 运行项目

```powershell
cd D:\FIT5120_calmPath
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000/docs
```

## Stage 0 完成标准

- FastAPI 可以启动
- `/health` 返回 `{"status": "ok"}`
- `/docs` 可以打开

如果这一步失败，不进入下一步。

---

# Stage 1 - 创建 User Story 分支

## 目标

为这个 User Story 创建独立开发分支。

```powershell
git switch main
git switch -c feature/US-refuge-search
```

如果团队已经开始使用 `development`，则从 `development` 创建：

```powershell
git switch development
git pull origin development
git switch -c feature/US-refuge-search
```

## 分支规则

```text
feature/US-refuge-search → development
```

不要直接 push 到 `main` 或 `development`。

---

# Stage 2 - 确认最小 API

## 目标

先确定前端需要调用什么接口。

## API 1：搜索附近 refuge

```text
GET /api/v1/refuges/nearby
```

请求参数：

```text
latitude   用户当前位置纬度
longitude  用户当前位置经度
radius_m   搜索半径，单位为米
```

示例：

```text
GET /api/v1/refuges/nearby?latitude=-37.8136&longitude=144.9631&radius_m=2000
```

成功返回：

```json
{
  "items": [
    {
      "id": "refuge-001",
      "name": "Carlton Gardens",
      "type": "park",
      "distance_m": 650,
      "latitude": -37.8061,
      "longitude": 144.9717
    }
  ]
}
```

## API 2：查看 refuge 详细地址

```text
GET /api/v1/refuges/{refuge_id}
```

示例：

```text
GET /api/v1/refuges/refuge-001
```

成功返回：

```json
{
  "id": "refuge-001",
  "name": "Carlton Gardens",
  "type": "park",
  "address": "1-111 Carlton Street, Carlton VIC 3053",
  "latitude": -37.8061,
  "longitude": 144.9717
}
```

## 需要和前端确认的内容

只确认以下问题：

1. 前端是否可以提供用户的 latitude 和 longitude？
2. 地图是否需要 latitude 和 longitude？
3. `radius_m` 使用米是否可以？
4. refuge 类型是否使用 `park`、`library`、`quiet_public_space`？
5. 前端是否接受上面的 JSON 格式？

如果前端同意，这个 API 设计就暂时冻结，不要频繁改变。

## Stage 2 完成标准

- API 路径确定
- 请求参数确定
- 返回字段确定
- 前端确认可以使用

---

# Stage 3 - 先用假数据完成接口

## 目标

不等待数据库，先让接口真正运行。

## 需要创建或修改的文件

```text
app/schemas/refuge.py
app/api/routes/refuges.py
```

## 这一阶段只完成

- 接收 latitude、longitude、radius_m
- 返回一组假 refuge 数据
- 可以在 `/docs` 中点击测试
- 返回格式和 Stage 2 完全一致

## 不做

- 不连接真实数据库
- 不接 Melbourne 数据集
- 不做复杂距离算法
- 不做地图页面

## Stage 3 完成标准

使用 `/docs` 调用 API 后，可以看到至少一个 refuge，并且包含：

```text
id
name
type
distance_m
latitude
longitude
```

---

# Stage 4 - 编写 API 自动化测试

## 目标

确认接口不会因为后续修改而坏掉。

## 需要创建或修改的文件

```text
tests/test_refuges.py
```

至少测试：

1. 正常搜索可以返回 200。
2. 返回结果包含名称、类型、距离和坐标。
3. 缺少 latitude 时返回验证错误。
4. 半径无效时返回验证错误。
5. 查询具体 refuge 时可以返回完整地址。
6. 不存在的 refuge 返回 404。

## Stage 4 完成标准

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

所有测试通过。

---

# Stage 5 - 和数据库开发者确认数据

## 目标

确认真实数据如何进入 backend。

数据库开发者需要确认：

1. 数据集是否已经下载或导入？
2. 每个 refuge 是否有唯一 ID？
3. 是否有 name、type、address？
4. 是否有 latitude 和 longitude？
5. 数据库中的类型值是什么？
6. 数据是否需要定期更新？
7. backend 应该查询哪张表或哪个接口？

## 预期的标准数据字段

```text
id
name
type
address
latitude
longitude
source
updated_at
```

如果真实数据还没有准备好，不要停工。继续使用假数据完成 API 和测试，同时记录数据缺口。

## Stage 5 完成标准

- 数据库字段已经确认
- 数据来源已经确认
- backend 知道如何查询 refuge
- 假数据可以被真实查询替换

---

# Stage 6 - 接入真实数据

## 目标

将 Stage 3 的假数据替换成真实数据库查询。

## 需要创建或修改的文件

```text
app/models/refuge.py
app/services/refuge_service.py
app/api/routes/refuges.py
```

简单分工：

```text
models/refuge.py
    描述数据库中的 refuge 数据

services/refuge_service.py
    查询附近 refuge、计算距离、整理返回数据

routes/refuges.py
    接收请求并调用 service
```

API 返回格式不要因为数据库字段不同而改变。数据库内部字段可以不同，但对前端的 API 合同保持稳定。

## Stage 6 完成标准

- API 返回真实数据
- 搜索结果只包含指定半径内的 refuge
- 每个结果包含名称、类型、距离和坐标
- 选择 refuge 可以返回完整地址
- 没有结果时有明确的空结果行为

---

# Stage 7 - 前端联调

## 目标

让前端真正调用 backend API。

## 联调顺序

1. 前端请求 `/api/v1/refuges/nearby`。
2. 前端将结果显示在列表中。
3. 前端使用 latitude 和 longitude 显示地图点。
4. 用户点击地图点或列表项。
5. 前端请求 `/api/v1/refuges/{refuge_id}`。
6. 前端显示完整地址。

## 联调时只处理当前 User Story 的问题

例如：

- 字段名称不一致
- 坐标格式不一致
- 前端需要的字段缺失
- 空结果如何显示

不要在联调阶段加入新的 User Story。

---

# Stage 8 - Pull Request

## 提交前检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
git status
```

## 提交代码

```powershell
git add app tests docs
git commit -m "feat: implement sensory refuge search"
git push -u origin feature/US-refuge-search
```

## Pull Request

创建：

```text
feature/US-refuge-search → development
```

PR 描述写清楚：

```text
实现了 sensory refuge 搜索 User Story。

已完成：
- 搜索附近 refuge
- 返回名称、类型、距离和坐标
- 查看 refuge 完整地址
- 添加自动化测试
- 已完成前端联调 / 尚未完成前端联调
```

## Review 要求

至少一名其他后端开发人员 review：

- API 是否符合 User Story
- 返回数据是否足够前端使用
- 数据库查询是否正确
- 测试是否覆盖主要情况
- 是否加入了不属于当前范围的功能

Review 通过并且 CI 通过后，才合并到 `development`。

---

# 最终完成标准

只有满足以下条件，这个 User Story 才算完成：

- [ ] API 路径已经确认
- [ ] 前端知道如何调用 API
- [ ] backend 可以启动
- [ ] `/docs` 可以测试 API
- [ ] 搜索结果包含名称、类型、距离和坐标
- [ ] 可以查看 refuge 完整地址
- [ ] 真实数据已经接入，或者数据缺口已明确记录
- [ ] 自动化测试通过
- [ ] 前端已经完成基本联调
- [ ] PR review 通过
- [ ] PR 已合并到 `development`

# 停止规则

遇到下面情况时，停止继续扩展功能，先解决当前问题：

- API 路径或返回格式还没有和前端确认
- 不知道数据库字段来自哪里
- 测试失败
- 真实数据不可用
- 想加入路线规划、拥挤检测或 sensory indicator
- 发现需要修改其他 User Story 的代码

当前项目的主线只有一句话：

> 先让前端能够搜索并显示附近 sensory refuge，再接入真实数据，最后通过 PR 合并。
